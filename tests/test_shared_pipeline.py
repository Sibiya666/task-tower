"""Host identity delivery, never imported stage receipts or live pilot evidence."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from tests import test_pipeline_policy as policy_fixture
from tests import test_shared_worker_review as worker_fixture
from task_tower.pipeline_journal import PipelineJournal
from task_tower.shared_queue import SharedQueue, digest


class SharedPipelinePolicyTests(unittest.TestCase):
    setUp = policy_fixture.PipelinePolicyTests.setUp
    load = policy_fixture.PipelinePolicyTests.load
    # Reuse the real private-policy/Git fixture, without inheriting its tests.
    def test_shared_delivery_requires_windows_and_explicit_policy(self):
        self.row['shared_worker'] = True
        with self.assertRaises(ValueError):
            self.load()
        self.row['ci_substitution'] = dict(enabled=True, required_platforms=['windows'])
        self.assertTrue(self.load()['tasks'][0]['shared_worker'])
        for invalid in (1, 'true', False):
            self.row['shared_worker'] = invalid
            with self.assertRaises(ValueError):
                self.load()


class SharedPipelineTests(unittest.TestCase):
    def setUp(self):
        worker_fixture.ReviewBlockerTests.setUp(self)
        self.settings['allowlist']=[dict(repository='owner/repo',issue=n,task_id='TT-SHARED-'+str(n)) for n in (1,2,3)]
        self.settings['harness'] = dict(kind='pipeline', connections=str(self.root/'connections.json'),
            config=str(self.root/'pipeline.json'), executor_config=str(self.root/'executor.json'),
            journal=str(self.root/'pipeline.db'))

    def test_handoff_delivers_identity_without_launching_model_or_forging_history(self):
        from task_tower.shared_worker import SharedWorker
        from task_tower.pipeline_shared import deliver
        received = []
        def delivery(task, settings, *, expected):
            received.append(copy.deepcopy(task))
            # Ownership remains pending until the worker binds the chosen run.
            ref = self.server.refs['refs/heads/task-tower/claims/issue-1001']
            self.assertIn('execution_intent', self.server.commits[ref]['message'])
            return dict(version=1, delivery_id=task['claim_id'], status='accepted', receipt_id=str(uuid.uuid4()))
        with patch('task_tower.pipeline_shared.validate_installation',return_value='f'*64), patch('task_tower.pipeline_shared.deliver', side_effect=delivery):
            worker = SharedWorker(self.queue, self.settings)
            result = worker.run_once()
        self.assertEqual(result['state'], 'awaiting_acceptance')
        self.assertIsNone(result['head_sha'])
        self.assertEqual(len(received), 1)
        self.assertFalse(list((self.root/'worker').rglob('capture/process.json')))
        self.assertFalse((self.root/'worker/execution-fence.json').exists())
        # New process/session cannot regain the claim, even if assignee is cleared.
        self.server.issues[1]['assignees'] = []
        restarted = SharedQueue(self.server.store(), str(uuid.uuid4()), allowlist=[dict(repository='owner/repo', issue=1, task_id='TT-SHARED-1')], assignee='operator')
        self.assertIsNone(restarted.claim(1))

    def test_lost_delivery_outcome_retains_fence_and_restart_cannot_replay(self):
        from task_tower.shared_worker import SharedWorker
        with patch('task_tower.pipeline_shared.validate_installation',return_value='f'*64), patch('task_tower.pipeline_shared.deliver', side_effect=OSError('lost response')):
            worker = SharedWorker(self.queue, self.settings)
            with self.assertRaises(OSError):
                worker.run_once()
            self.assertTrue(worker.fence.exists())
            self.assertFalse(list(worker.root.glob('*/outcome.json')))
            with self.assertRaises(ValueError):
                SharedWorker(self.queue, self.settings)
        self.assertEqual(len(self.server.refs), 1)

    def test_lost_final_cas_response_preserves_confirmed_run_and_worker_fence(self):
        from task_tower.shared_worker import SharedWorker
        run_id=str(uuid.uuid4())
        def delivered(task,settings,*,expected):
            self.server.lose_intent=True
            return dict(version=1,delivery_id=task['claim_id'],status='accepted',receipt_id=run_id)
        with patch('task_tower.pipeline_shared.validate_installation',return_value='f'*64),patch('task_tower.pipeline_shared.deliver',side_effect=delivered):
            worker=SharedWorker(self.queue,self.settings)
            with self.assertRaises(Exception):worker.run_once()
            self.assertTrue(worker.fence.exists())
            with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        ref=self.server.refs['refs/heads/task-tower/claims/issue-1001']
        body=json.loads(self.server.commits[ref]['message'].split('\n',1)[1])
        self.assertEqual(body['handoff']['run_id'],run_id)
        self.assertEqual(body['state'],'awaiting_acceptance')
        self.assertEqual(len(self.server.refs),1)


class DeliveryTests(unittest.TestCase):
    load = policy_fixture.PipelinePolicyTests.load
    def setUp(self):
        policy_fixture.PipelinePolicyTests.setUp(self)
        from tests.test_shared_worker import WorkServer
        self.server = WorkServer(self.sha, 'b'*40)
        self.addCleanup(self.server.close)
        self.row.update(issue=1, task_id='TT-SHARED-1', shared_worker=True)
        self.row['ci_substitution'] = dict(enabled=True, required_platforms=['windows'])
        self.executor['allowlist'][0].update(issue=1, task_id='TT-SHARED-1')
        self.config = self.load()
        self.journal = PipelineJournal(self.root/'pipeline.db')
        self.queue = SharedQueue(self.server.store(), str(uuid.uuid4()), allowlist=[dict(repository='owner/repo', issue=1, task_id='TT-SHARED-1')], assignee='operator')
        claim = self.queue.claim(1)
        self.assertTrue(self.queue.assign(claim))
        self.permit = self.queue.start(claim)
        self.task = self.queue.consume(self.permit)
        store = self.server.store()
        request = store.request
        # Fixture only: production still uses the real GitHub reader.
        store.request = lambda method, path, body=None: [] if '/comments' in path else request(method, path, body)
        issue = store.get(1)
        self.snapshot_data = {'owner/repo': dict(connection=self.connections[0], store=store, source=object(),
            issues={1:issue}, metadata={1:store.metadata(issue)}, index={'TT-SHARED-1':[1]}, error=None)}
        from task_tower.pipeline_shared import consumer_binding
        self.binding=consumer_binding(self.config,self.journal)
        self.config['_shared_journal']=self.journal

    def delivery(self):
        from task_tower.pipeline_shared import deliver
        with patch('task_tower.pipeline_shared._installation', return_value=(self.config, self.journal)), patch('task_tower.dispatch_selection.collect_snapshot', return_value=self.snapshot_data):
            return deliver(self.task, {},expected=self.binding)

    def confirm(self,receipt):
        self.queue.finish(self.permit,'awaiting_acceptance','c'*64,handoff=dict(version=1,kind='pipeline',consumer_sha256=self.binding,run_id=receipt['receipt_id']))

    def test_delivery_queues_one_real_run_with_empty_stage_history(self):
        from task_tower.pipeline_shared import deliver
        with patch('task_tower.pipeline_shared._installation', return_value=(self.config, self.journal)), patch('task_tower.dispatch_selection.collect_snapshot', return_value=self.snapshot_data):
            receipt = deliver(self.task, {},expected=self.binding)
        self.assertEqual(receipt['status'], 'accepted')
        run = self.journal.status(receipt['receipt_id'])
        self.assertEqual(run['delivery_id'], self.task['claim_id'])
        self.assertEqual((run['state'], run['stage']), ('queued', 'spec'))
        history = self.journal.history(run['run_id'])
        for key in ('attempts', 'verdicts', 'effects'):
            self.assertEqual(history[key], [])
        self.confirm(receipt)
        # A terminal result never grants permission to deliver again.
        with patch('task_tower.pipeline_shared._installation', return_value=(self.config, self.journal)), patch('task_tower.dispatch_selection.collect_snapshot', return_value=self.snapshot_data):
            with self.assertRaises(ValueError):deliver(self.task, {},expected=self.binding)
        self.assertEqual(len(self.journal.status()['runs']), 1)

    def test_changed_claim_criteria_base_or_assignee_cannot_admit(self):
        from task_tower.pipeline_shared import deliver
        for field, value in (('claim_id', str(uuid.uuid4())), ('issue_id', 9000), ('base_sha', 'a'*40), ('criteria_sha256', '0'*64), ('worker_session', str(uuid.uuid4()))):
            with self.subTest(field=field), patch('task_tower.pipeline_shared._installation', return_value=(self.config, self.journal)), patch('task_tower.dispatch_selection.collect_snapshot', return_value=self.snapshot_data):
                with self.assertRaises(ValueError):
                    deliver(dict(self.task, **{field:value}), {},expected=self.binding)
        self.assertFalse(self.journal.path.exists())

    def test_pipeline_admission_rechecks_shared_claim_not_just_delivery_json(self):
        from task_tower.pipeline_policy import admission_authorized
        task = self.config['tasks'][0]
        self.assertIsNone(admission_authorized(self.config, task, self.snapshot_data))
        receipt=self.delivery();self.confirm(receipt)
        self.assertIsNotNone(admission_authorized(self.config, task, self.snapshot_data, delivery_id=self.task['claim_id'],run_id=receipt['receipt_id']))
        self.server.issues[1]['assignees'] = []
        self.snapshot_data['owner/repo']['issues'][1]['assignees'] = []
        self.assertIsNone(admission_authorized(self.config, task, self.snapshot_data, delivery_id=self.task['claim_id'],run_id=receipt['receipt_id']))

    def test_legacy_completion_and_ordinary_dispatch_never_authorize_new_execution(self):
        from task_tower.pipeline import adapter
        from task_tower.pipeline_policy import admission_authorized
        task = self.config['tasks'][0]
        receipt = adapter(dict(operation='submit', delivery_id=self.task['claim_id'],
            repository='owner/repo', issue=1, task_id='TT-SHARED-1', runner_label='local'), self.config, self.journal)
        self.assertEqual(receipt['status'], 'unknown')
        self.assertFalse(self.journal.path.exists())
        self.queue.finish(self.permit,'awaiting_acceptance','c'*64)
        self.assertIsNone(admission_authorized(self.config, task, self.snapshot_data, delivery_id=self.task['claim_id']))

    def test_unconfirmed_or_foreign_journal_run_waits_without_model_or_owner(self):
        from task_tower.pipeline_worker import step
        receipt=self.delivery()
        with patch('task_tower.dispatch_selection.collect_snapshot',return_value=self.snapshot_data):
            report=step(self.config,self.journal)
        self.assertEqual(report['status'],'unavailable')
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'queued')
        self.assertIsNone(self.journal.status(receipt['receipt_id'])['owner_id'])
        self.assertEqual(self.journal.history(receipt['receipt_id'])['attempts'],[])
        self.confirm(receipt)
        from task_tower.pipeline_policy import admission_authorized
        task=self.config['tasks'][0]
        self.assertIsNone(admission_authorized(self.config,task,self.snapshot_data,delivery_id=self.task['claim_id'],run_id=str(uuid.uuid4())))
        other=PipelineJournal(self.root/'another.db')
        self.assertIsNone(admission_authorized(dict(self.config,_shared_journal=other),task,self.snapshot_data,delivery_id=self.task['claim_id'],run_id=receipt['receipt_id']))

    def test_installation_identity_and_plan_are_checked_before_claim_or_delivery(self):
        from task_tower.pipeline_shared import validate_installation,deliver
        with patch('task_tower.pipeline_shared._installation',return_value=(self.config,self.journal)):
            with self.assertRaises(ValueError):validate_installation({},'owner/repo',{'1':'docs/plan.md'},[dict(repository='owner/repo',issue=1,task_id='TT-WRONG-1')])
            self.assertEqual(validate_installation({},'owner/repo',{'1':'docs/plan.md'},[dict(repository='owner/repo',issue=1,task_id='TT-SHARED-1')]),self.binding)
            with self.assertRaises(ValueError):deliver(self.task,{},expected='0'*64)

    def test_relative_private_paths_fail_before_loading_any_configuration(self):
        from task_tower.pipeline_shared import _installation
        with patch('task_tower.pipeline._runtime') as runtime:
            with self.assertRaises(ValueError):
                _installation(dict(kind='pipeline', connections='relative.json', config='pipeline.json', executor_config='executor.json', journal='journal.db'))
            runtime.assert_not_called()


class ExistingPipelineIntegrationTests(unittest.TestCase):
    def test_confirmed_handoff_runs_existing_roles_checks_and_local_pr_consumer(self):
        from tests import test_pipeline_worker as engine_fixture
        from tests.test_shared_worker import WorkServer
        from task_tower.pipeline_shared import deliver,consumer_binding
        from task_tower.pipeline_worker import step
        from task_tower.pipeline_publish import publish_one
        engine=engine_fixture.WorkerTests();engine.setUp();self.addCleanup(engine.doCleanups)
        f=engine.fixture
        f.row.update(issue=1,task_id='TT-SHARED-1',shared_worker=True)
        f.row['ci_substitution']=dict(enabled=True,required_platforms=['windows'])
        f.executor['allowlist'][0].update(issue=1,task_id='TT-SHARED-1')
        config=f.load();journal=PipelineJournal(f.root/'handoff.db')
        server=WorkServer(f.sha,'b'*40);self.addCleanup(server.close)
        store=server.store();request=store.request
        store.request=lambda method,path,body=None: [] if '/comments' in path else request(method,path,body)
        queue=SharedQueue(store,str(uuid.uuid4()),allowlist=[dict(repository='owner/repo',issue=1,task_id='TT-SHARED-1')],assignee='operator')
        claim=queue.claim(1);self.assertTrue(queue.assign(claim));permit=queue.start(claim);task=queue.consume(permit)
        binding=consumer_binding(config,journal)
        def snapshot(_):
            issue=store.get(1)
            return {'owner/repo':dict(connection=f.connections[0],store=store,source=object(),issues={1:issue},
                metadata={1:store.metadata(issue)},index={'TT-SHARED-1':[1]},error=None)}
        config['_publisher']=lambda *args:publish_one(*args,store_factory=lambda _:store)
        with patch('task_tower.pipeline_shared._installation',return_value=(config,journal)),patch('task_tower.dispatch_selection.collect_snapshot',side_effect=snapshot):
            receipt=deliver(task,{},expected=binding)
            self.assertEqual(step(config,journal)['status'],'unavailable')
            queue.finish(permit,'awaiting_acceptance','c'*64,handoff=dict(version=1,kind='pipeline',consumer_sha256=binding,run_id=receipt['receipt_id']))
            owner=str(uuid.uuid4())
            for _ in range(24):
                report=step(config,journal,owner_id=owner)
                if report['status'] in ('ready_for_pr','needs_input','unknown'):break
        self.assertEqual(report['status'],'ready_for_pr',report)
        history=journal.history(receipt['receipt_id'])
        self.assertEqual([a['role'] for a in history['attempts'] if a['role']!='host_check'],[
            'spec_executor','spec_reviewer','development_executor','development_reviewer','test_executor','test_reviewer'])
        self.assertEqual(len({a['instance_id'] for a in history['attempts']}),7)
        self.assertTrue(all(a['evidence']['cleanup_confirmed'] for a in history['attempts']))
        self.assertEqual([v['decision'] for v in history['verdicts']],['approve']*3)
        self.assertEqual(server.issues[1]['state'],'open')
        self.assertFalse(any(path=='/pulls' for _,path,_ in server.posts))

