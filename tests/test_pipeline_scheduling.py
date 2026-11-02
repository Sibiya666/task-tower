"""Fresh host priority selection and atomic journal ordering, never authority."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from task_tower import pipeline, pipeline_worker as worker
from task_tower.pipeline_journal import PipelineJournal
from task_tower.executor_profiles import profile_fingerprint
from task_tower.github_tasks import replace_metadata
from tests import test_pipeline_journal as jf
from tests import test_pipeline_default_source as sf


def hint(repository,issue,priority):return dict(repository=repository,issue=issue,priority=priority)


class JournalOrderingTests(jf.JournalFixture,unittest.TestCase):
    def submit(self,repository,issue):
        return self.journal.submit(dict(jf.request(issue),repository=repository),jf.policy())

    def test_priority_precedes_issue_repository_and_reverse_delivery_order(self):
        self.submit('a/repo',1);self.submit('z/repo',20)
        run=self.journal.claim(jf.uid(),2,queued_order=[hint('a/repo',1,'P3'),hint('z/repo',20,'P1')])
        self.assertEqual((run['repository'],run['issue']),('z/repo',20))

    def test_ties_sort_by_repository_issue_not_hint_or_delivery_order(self):
        self.submit('z/repo',1);self.submit('a/repo',20);self.submit('a/repo',2)
        run=self.journal.claim(jf.uid(),2,queued_order=[hint('z/repo',1,'P1'),hint('a/repo',20,'P1'),hint('a/repo',2,'P1')])
        self.assertEqual((run['repository'],run['issue']),('a/repo',2))

    def test_conflicting_high_priority_skips_to_verified_other_repository(self):
        self.submit('a/repo',1);self.journal.claim(jf.uid(),2)
        self.submit('a/repo',2);self.submit('z/repo',3)
        run=self.journal.claim(jf.uid(),2,queued_order=[hint('a/repo',2,'P0'),hint('z/repo',3,'P3')])
        self.assertEqual(run['repository'],'z/repo')

    def test_absent_newly_queued_rows_wait_for_fresh_hint(self):
        self.submit('a/repo',1)
        old=[hint('a/repo',1,'P3')]
        self.submit('z/repo',20)
        self.assertIsNone(self.journal.claim(jf.uid(),2,queued_order=[]))
        self.assertEqual(self.journal.claim(jf.uid(),2,queued_order=old)['repository'],'a/repo')
        self.assertIsNone(self.journal.claim(jf.uid(),2,queued_order=old))
        self.assertEqual(self.journal.claim(jf.uid(),2,queued_order=[hint('z/repo',20,'P0')])['repository'],'z/repo')

    def test_malformed_hints_reject_without_changing_any_journal_bytes(self):
        self.submit('a/repo',1);before=self.path.read_bytes()
        good=hint('a/repo',1,'P3')
        bad=[{},'bad',True,[dict(good,extra=1)],[dict(good,repository='A/repo')],
             [dict(good,issue=True)],[dict(good,issue=0)],[dict(good,issue=1.0)],
             [dict(good,priority='P4')],[dict(good,priority=None)],[good,good],[good]*10001]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):self.journal.claim(jf.uid(),2,queued_order=value)
            self.assertEqual(self.path.read_bytes(),before)

    def test_safe_ready_precedes_new_p0_and_empty_hint(self):
        case=jf.ReadyResumeTests();case.setUp();self.addCleanup(case.doCleanups)
        owner=jf.uid()
        with case.journal.owner(owner):
            ready=case.ready(owner)
            case.journal.submit(dict(jf.request(99),repository='other/repo'),jf.policy())
            resumed=case.journal.claim(owner,2,queued_order=[hint('other/repo',99,'P0')])
            self.assertEqual(resumed['run_id'],ready['run_id'])
            self.assertEqual(case.journal.claim(owner,2,queued_order=[])['run_id'],ready['run_id'])

    def test_queued_denial_has_no_owner_deadline_or_execution_history(self):
        receipt=self.submit('a/repo',1);old=self.journal.status(receipt['receipt_id'])
        denied=self.journal.deny_queued(old)
        self.assertEqual((denied['state'],denied['reason']),('needs_input','policy_revoked'))
        for key in old.keys()-{'state','reason','updated_at'}:self.assertEqual(denied[key],old[key],key)
        history=self.journal.history(old['run_id'])
        self.assertEqual(history['attempts'],[]);self.assertEqual(history['effects'],[]);self.assertEqual(history['verdicts'],[])
        self.assertEqual([e['kind'] for e in history['events']],['submitted','transition'])
        self.assertIsNone(self.journal.deny_queued(old))
        self.assertEqual(self.journal.history(old['run_id']),history)

    def test_denial_skips_stale_cancelled_active_or_unknown_rows(self):
        receipt=self.submit('a/repo',1);old=self.journal.status(receipt['receipt_id'])
        self.journal.cancel(old['run_id']);before=self.journal.status()
        self.assertIsNone(self.journal.deny_queued(old));self.assertEqual(self.journal.status(),before)
        self.submit('z/repo',2);run=self.journal.claim(jf.uid(),2)
        self.assertIsNone(self.journal.deny_queued(run))
        self.journal.record(run['run_id'],run['owner_id'],{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='unknown',reason='owner_dead'))
        unknown=self.journal.status(run['run_id']);self.assertIsNone(self.journal.deny_queued(unknown))
        self.assertEqual(self.journal.status(run['run_id']),unknown)

    def test_denial_rejects_clock_rollback_without_rewriting_bytes(self):
        import datetime
        from task_tower import pipeline_journal as module
        receipt=self.submit('a/repo',1);row=self.journal.status(receipt['receipt_id']);before=self.path.read_bytes()
        earlier=(datetime.datetime.fromisoformat(row['updated_at'])-datetime.timedelta(seconds=1)).isoformat()
        with patch.object(module,'_now',return_value=earlier),self.assertRaises(ValueError):self.journal.deny_queued(row)
        self.assertEqual(self.path.read_bytes(),before)


class WorkerOrderingTests(unittest.TestCase):
    def setUp(self):
        self.source=sf.DefaultSourceTests();self.source.setUp();self.addCleanup(self.source.doCleanups)
        f=self.source.fixture;self.fixture=f
        high=copy.deepcopy(f.row);high.update(issue=20,task_id='TT-PIPELINE-020')
        f.value['tasks'].append(high)
        f.executor['allowlist'].append(dict(f.executor['allowlist'][0],issue=20,task_id=high['task_id']))
        self.source.metadata['priority']='P3'
        self.source.issues[0]['body']=replace_metadata('Build from installed policy',self.source.metadata)
        self.high_metadata=dict(self.source.metadata,task_id=high['task_id'],priority='P1')
        self.source.issues.append(dict(number=20,id=200,state='open',title='Higher priority',body=replace_metadata('Build priority task',self.high_metadata)))
        self.config=f.load();self.source.config=self.config
        self.journal=PipelineJournal(f.root/'ordered.db',checkouts=(f.connections[0].checkout,))
        self.owner=str(uuid.uuid4())
        self.submit(20);self.submit(16)

    def submit(self,issue):
        task=next(t for t in self.config['tasks'] if t['issue']==issue)
        profile=self.config['profiles'][task['executor_profile']]
        envelope=dict(profile_id=task['executor_profile'],profile_fingerprint=profile_fingerprint(profile),policy_sha256=self.config['policy_sha256'],component_keys=task['components'],limits={k:self.config[k] for k in ('task_timeout_seconds','role_timeout_seconds','max_reworks','max_processes','log_max_bytes')})
        return self.journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=issue,task_id=task['task_id'],runner_label='local'),envelope)

    def test_genuine_host_selection_starts_higher_issue_priority_first(self):
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(answer['run_id'])['issue'],20)
        self.assertEqual(answer['status'],'ready')
        self.assertEqual(self.journal.status(answer['run_id'])['process_count'],0)

    def test_source_unavailable_is_not_idle_and_claims_nothing(self):
        before=self.journal.status();self.source.transport_unavailable=True
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual((answer['status'],answer['reason'],answer['run_id']),('unavailable','source_unavailable',None))
        self.assertEqual(self.journal.status(),before)
        pipeline._host_result(answer,'_action')

    def test_actual_unverified_dependency_excludes_high_priority(self):
        self.high_metadata.update(priority='P0',blocked_by=['Owner/Repo#17'])
        self.source.issues[1]['body']=replace_metadata('Build priority task',self.high_metadata)
        dep=dict(version=1,kind='task',mode='autonomous',task_id='TT-DEPENDENCY-001',status='done')
        self.source.issues.append(dict(number=17,id=201,state='closed',title='Unverified dependency',body=replace_metadata('Model prose claims done',dep)))
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(answer['run_id'])['issue'],16)
        denied=next(r for r in self.journal.status()['runs'] if r['issue']==20)
        self.assertEqual((denied['state'],denied['reason']),('needs_input','policy_revoked'))
        self.assertIsNone(denied['owner_id']);self.assertIsNone(denied['deadline_at'])

    def test_invalid_p4_is_not_normalized_to_any_allowed_priority(self):
        self.high_metadata['priority']='P4'
        self.source.issues[1]['body']=replace_metadata('Build priority task',self.high_metadata)
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(answer['run_id'])['issue'],16)
        self.assertEqual(answer['reason'],'source_unavailable')

    def test_genuine_absent_priority_uses_selector_p3_default(self):
        self.high_metadata.pop('priority')
        self.source.issues[1]['body']=replace_metadata('Build priority task',self.high_metadata)
        with self.source.transport():order,failed,_=worker._queued_selection(self.config)
        self.assertFalse(failed)
        self.assertEqual(order,[hint('owner/repo',16,'P3'),hint('owner/repo',20,'P3')])

    def assert_all_denied_without_execution(self,config=None):
        with self.source.transport():answer=worker.step(config or self.config,self.journal,owner_id=self.owner)
        self.assertEqual((answer['status'],answer['reason']),('needs_input','policy_revoked'))
        for row in self.journal.status()['runs']:
            self.assertEqual(row['state'],'needs_input');self.assertIsNone(row['owner_id']);self.assertIsNone(row['deadline_at'])
            self.assertEqual(row['process_count'],0)
            history=self.journal.history(row['run_id'])
            self.assertEqual(history['effects'],[]);self.assertEqual(history['attempts'],[])

    def test_fresh_closed_queued_issues_are_visible_denials_not_idle(self):
        for row in self.source.issues:row['state']='closed'
        self.assert_all_denied_without_execution()

    def test_fresh_manual_mode_queued_issues_are_denied(self):
        for row,meta in zip(self.source.issues,(self.source.metadata,self.high_metadata)):
            meta['mode']='manual';row['body']=replace_metadata('Actual task criteria',meta)
        self.assert_all_denied_without_execution()

    def test_private_policy_drift_is_denied_without_execution(self):
        self.fixture.value['max_active']=1
        self.assert_all_denied_without_execution(self.fixture.load())

    def test_private_profile_drift_is_denied_without_execution(self):
        self.fixture.profile['max_attempts']=self.fixture.profile.get('max_attempts',1)+1
        self.assert_all_denied_without_execution(self.fixture.load())

    def test_new_criteria_before_first_admission_are_captured_fresh(self):
        self.source.issues[1]['body']=replace_metadata('Fresh criteria before first admission',self.high_metadata)
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        run=self.journal.status(answer['run_id'])
        self.assertEqual((run['issue'],run['state']),(20,'ready'))
        self.assertIn('Fresh criteria before first admission',run['admission']['criteria']['body'])

    def test_new_arrival_absent_from_pre_source_rows_waits_for_next_pass(self):
        task=copy.deepcopy(self.config['tasks'][0]);task.update(issue=30,task_id='TT-NEW-030')
        self.fixture.value['tasks'].append(task)
        self.fixture.executor['allowlist'].append(dict(self.fixture.executor['allowlist'][0],issue=30,task_id=task['task_id']))
        self.config=self.fixture.load()
        meta=dict(self.source.metadata,task_id=task['task_id'],priority='P0')
        self.source.issues.append(dict(number=30,id=300,state='closed',title='New arrival',body=replace_metadata('New source row',meta)))
        for issue in self.source.issues:issue['state']='closed'
        original=self.source.http;inserted=[]
        def transport(*args,**kwargs):
            if not inserted:inserted.append(self.submit(30))
            return original(*args,**kwargs)
        self.source.http=transport
        with self.source.transport():worker.step(self.config,self.journal,owner_id=self.owner)
        row=self.journal.status(inserted[0]['receipt_id'])
        self.assertEqual(row['state'],'queued');self.assertIsNone(row['owner_id'])
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(answer['run_id'],row['run_id']);self.assertEqual(answer['status'],'needs_input')

    def test_dependency_repository_unavailable_is_not_a_clean_denial(self):
        from task_tower.project_connections import ProjectConnection
        checkout=self.fixture.root/'missing-dependency';checkout.mkdir()
        self.fixture.connections.append(ProjectConnection(id='dependency',repository='broken/repo',checkout=checkout,runner_label='local'))
        self.config=self.fixture.load()
        self.high_metadata['blocked_by']=['broken/repo#17']
        self.source.issues[1]['body']=replace_metadata('Build priority task',self.high_metadata)
        original=self.source.http
        def transport(method,url,*args):
            if '/repos/broken/repo/' in url:raise OSError('dependency source unavailable')
            return original(method,url,*args)
        self.source.http=transport
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(answer['run_id'])['issue'],16)
        waiting=next(r for r in self.journal.status()['runs'] if r['issue']==20)
        self.assertEqual(waiting['state'],'queued');self.assertIsNone(waiting['owner_id'])
        self.assertEqual(answer['reason'],'source_unavailable')

    def test_partial_artifact_failure_preserves_queue_and_freezes_actual_source_errors(self):
        import hashlib
        import zipfile
        from urllib.parse import urlsplit
        from task_tower.github_source import GitHubSource
        from task_tower.merge_events import build_merge_event
        from task_tower.project_worker import LIFECYCLE,verified_done
        from task_tower.dispatch_selection import collect_snapshot
        from tests.test_github_source import GitHubSourceTests
        base_pr,base_run,_=GitHubSourceTests().fixture()
        repository=self.fixture.connections[0].repository
        pulls={};runs=[];archives={}
        for run_id,number,sha,task in ((202,7,'a'*40,'TT-DEPENDENCY-001'),(303,8,'b'*40,'TT-OTHER-001')):
            pr=copy.deepcopy(base_pr);pr.update(number=number,merge_commit_sha=sha,body='Task-Tower: '+task);pr['head']['sha']=sha;pr['base']['repo']['full_name']=repository;pulls[number]=pr
            runs.append(dict(base_run,id=run_id,head_sha=sha,repository=dict(full_name=repository),pull_requests=[dict(number=number)]))
            event=build_merge_event(dict(action='closed',repository=dict(full_name=repository),pull_request=pr),repository,'linux','passed',run_id,2)
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive:archive.writestr('merge-event.json',json.dumps(event))
            archives[run_id]=output.getvalue()
        fault=[False];reads=[0]
        def merges(url,headers,limit):
            path=urlsplit(url).path
            if path.endswith('/actions/workflows/postmerge.yml/runs'):value=dict(workflow_runs=runs)
            elif path.endswith('/artifacts'):
                run_id=int(path.split('/')[-2]);reads[0]+=int(run_id==202)
                if run_id==202 and fault[0] and reads[0]==1:value=dict(artifacts=[])
                else:
                    number=7 if run_id==202 else 8;sha='a'*40 if run_id==202 else 'b'*40
                    value=dict(artifacts=[dict(id=run_id,name='task-tower-merge-'+str(number)+'-linux',expired=False,workflow_run=dict(id=run_id,head_sha=sha))])
            elif '/actions/artifacts/' in path:return archives[int(path.split('/')[-2])]
            elif '/pulls/' in path:value=pulls[int(path.rsplit('/',1)[1])]
            else:raise AssertionError('unexpected merge fixture route')
            return json.dumps(value).encode()
        baseline=GitHubSource(repository,transport=merges).poll()
        bundle=next(b for b in baseline if b['run_id']=='202')
        digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        evidence={stage:dict(sha256='d'*64,reviewer='reviewer',evidence='docs/review.md') for stage in ('spec','development','test','postmerge')}
        receipt=dict(version=1,kind='local-postmerge',repository=repository,issue=17,issue_id=201,task_id='TT-DEPENDENCY-001',commit='a'*40,bundle=bundle,review=dict(verdict='approve',task_id='TT-DEPENDENCY-001',commit='a'*40,summary='Verified baseline',findings=[]),required_platforms=['linux'],policy=dict(executor='executor',reviewer='reviewer'),input_snapshot='c'*64,evidence=evidence,evidence_digest=digest(evidence))
        attempt=dict(kind='local-postmerge',status='done',commit='a'*40,publication_id=digest(receipt),receipt=receipt)
        comment=dict(id=1,user=dict(login='owner'),body=LIFECYCLE+json.dumps(dict(status='done',remote_attempt=attempt))+'\n-->')
        dep=dict(version=1,kind='task',mode='autonomous',task_id='TT-DEPENDENCY-001',status='done')
        self.source.issues.append(dict(number=17,id=201,state='closed',title='Verified dependency',body=replace_metadata('Dependency',dep)))
        self.high_metadata['blocked_by']=['owner/repo#17'];self.source.issues[1]['body']=replace_metadata('Build priority task',self.high_metadata)
        original=self.source.http
        def transport(method,url,headers,payload,limit):
            path=urlsplit(url).path
            if '/issues/17/comments' in path:return json.dumps([comment]).encode()
            if '/compare/' in path:return json.dumps(dict(status='ahead')).encode()
            if '/actions/' in path or '/pulls/' in path:return merges(url,headers,limit)
            return original(method,url,headers,payload,limit)
        self.source.http=transport
        with self.source.transport():
            project=collect_snapshot(self.config['_connections'])['owner/repo']
            self.assertTrue(verified_done(project['connection'],project['store'],project['source'],project['issues'][17]))
        fault[0]=True;reads[0]=0
        with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(answer['run_id'])['issue'],16)
        waiting=next(r for r in self.journal.status()['runs'] if r['issue']==20)
        self.assertEqual(waiting['state'],'queued');self.assertIsNone(waiting['owner_id'])
        self.assertEqual(answer['reason'],'source_unavailable')
        self.assertEqual(reads[0],1,'classification must not re-poll away the captured partial error')

    def test_unrelated_source_failure_reports_warning_and_does_not_preempt_ready(self):
        from task_tower.project_connections import ProjectConnection
        checkout=self.fixture.root/'broken-checkout';checkout.mkdir()
        self.fixture.connections.append(ProjectConnection(id='broken',repository='broken/repo',checkout=checkout,runner_label='local',trusted_publishers=['owner']))
        self.config=self.fixture.load()
        original=self.source.http
        def transport(method,url,*args):
            if '/repos/broken/repo/' in url:raise OSError('fixture source unavailable')
            return original(method,url,*args)
        self.source.http=transport
        with self.source.transport():first=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(self.journal.status(first['run_id'])['issue'],20)
        self.assertEqual((first['status'],first['reason']),('ready','source_unavailable'))
        self.source.metadata['priority']='P0'
        self.source.issues[0]['body']=replace_metadata('Build from installed policy',self.source.metadata)
        with self.source.transport():second=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(second['run_id'],first['run_id'])
        self.assertEqual(second['reason'],'source_unavailable')
        self.assertEqual(self.journal.status(second['run_id'])['process_count'],1)

    def test_hint_cannot_grant_missing_private_mapping_or_create_effect(self):
        task=self.config['tasks'][0];profile=self.config['profiles']['local']
        envelope=dict(profile_id='local',profile_fingerprint=profile_fingerprint(profile),policy_sha256=self.config['policy_sha256'],component_keys=['other'],limits={k:self.config[k] for k in ('task_timeout_seconds','role_timeout_seconds','max_reworks','max_processes','log_max_bytes')})
        receipt=self.journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=99,task_id='TT-UNMAPPED-099',runner_label='local'),envelope)
        with self.journal.owner(self.owner):
            run=self.journal.claim(self.owner,2,queued_order=[hint('owner/repo',99,'P0')])
            self.assertEqual(run['run_id'],receipt['receipt_id'])
            with self.source.transport():answer=worker.step(self.config,self.journal,owner_id=self.owner)
        self.assertEqual(answer['status'],'needs_input')
        history=self.journal.history(run['run_id'])
        self.assertEqual(history['effects'],[]);self.assertEqual(history['attempts'],[])

    def test_http_reads_never_occur_inside_journal_transaction(self):
        entered=[];original=self.journal._db;http=self.source.http
        @contextlib.contextmanager
        def database(*args,**kwargs):
            with original(*args,**kwargs) as db:
                entered.append(True)
                try:yield db
                finally:entered.pop()
        def transport(*args,**kwargs):
            self.assertEqual(entered,[])
            return http(*args,**kwargs)
        self.source.http=transport
        with patch.object(self.journal,'_db',database),self.source.transport():worker.step(self.config,self.journal,owner_id=self.owner)


class SchedulingPublicReportTests(unittest.TestCase):
    @unittest.skipUnless(pipeline.native_execution_supported(),'Windows native pipeline execution')
    def test_cancel_before_claim_keeps_queue_unowned_without_effects(self):
        from tests.test_pipeline_watch import WatchTests
        case=WatchTests();case.setUp();self.addCleanup(case.doCleanups)
        request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=case.config['tasks'][0]['task_id'],runner_label='local')
        pipeline.adapter(request,case.config,case.journal)
        marker=case.root/'before-claim-read'
        value=json.loads(case.http.read_text());value.update(slow=True,started=str(marker));case.http.write_text(json.dumps(value))
        stop=threading.Event();host=pipeline._Host(case.args,'_action',30,stop)
        try:
            import time
            deadline=time.monotonic()+10
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(marker.exists());stop.set()
            self.assertTrue(host.done.wait(5));self.assertTrue(host.outcome['cleanup_confirmed'])
            case.journal.recover();run=case.journal.status()['runs'][0]
            self.assertEqual(run['state'],'queued');self.assertIsNone(run['owner_id'])
            self.assertEqual(run['process_count'],0)
            self.assertEqual(case.journal.history(run['run_id'])['effects'],[])
            self.assertEqual(case.journal.history(run['run_id'])['attempts'],[])
        finally:stop.set();host.done.wait(5);host.close()

    def test_unavailable_is_only_an_unbound_source_observation(self):
        report=dict(run_id=None,status='unavailable',stage=None,generation=None,reason='source_unavailable',input_sha256=None,receipt_sha256=None,effect_sha256=None)
        self.assertEqual(pipeline._host_result(report,'_action'),report)
        for changes in (dict(run_id=str(uuid.uuid4()),stage='spec',generation=1),dict(reason='cleanup_unknown'),dict(receipt_sha256='a'*64)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):pipeline._host_result(dict(report,**changes),'_action')

    @unittest.skipUnless(pipeline.native_execution_supported(),'Windows native pipeline execution')
    def test_real_public_work_source_failure_exits_one_without_claim(self):
        from tests.test_pipeline_watch import WatchTests
        case=WatchTests();case.setUp();self.addCleanup(case.doCleanups)
        request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=case.config['tasks'][0]['task_id'],runner_label='local')
        pipeline.adapter(request,case.config,case.journal)
        value=json.loads(case.http.read_text());value['unavailable']=True;case.http.write_text(json.dumps(value))
        before=case.journal.status();output=io.StringIO()
        with contextlib.redirect_stdout(output):code=pipeline.main([*pipeline._fixed(case.args,'work')[4:],'--once'])
        self.assertEqual(code,1)
        answer=json.loads(output.getvalue())
        self.assertEqual((answer['status'],answer['reason']),('unavailable','source_unavailable'))
        self.assertEqual(case.journal.status(),before)

    @unittest.skipUnless(pipeline.native_execution_supported(),'Windows native pipeline execution')
    def test_actual_unavailable_host_drives_queued_backoff_and_visible_health(self):
        from tests.test_pipeline_watch import WatchTests
        case=WatchTests();case.setUp();self.addCleanup(case.doCleanups)
        request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=case.config['tasks'][0]['task_id'],runner_label='local')
        pipeline.adapter(request,case.config,case.journal)
        value=json.loads(case.http.read_text());value['unavailable']=True;case.http.write_text(json.dumps(value))
        host=pipeline._Host(case.args,'_action',30,threading.Event())
        try:
            self.assertTrue(host.done.wait(30));self.assertEqual(host.result['status'],'unavailable')
            actual=host.result
        finally:host.close()
        case.start();state=case.config['_watch'];state['next_dispatch']=float('inf')
        class Finished:
            result=actual
            done=threading.Event()
            def close(self):pass
        Finished.done.set()
        for index,delay in enumerate((5,10,20,40,60,60),1):
            state['workers']=[Finished()]
            with patch('task_tower.pipeline.time.monotonic',return_value=100):health=pipeline.watch_tick(case.config,case.journal)
            self.assertEqual(state['action_failures'],index)
            self.assertEqual(state['next_queued_action'],100+delay)
            self.assertGreaterEqual(health['read_failures'],index)
            self.assertEqual(state['workers'],[])
        self.assertTrue(all(r['state']=='queued' and r['owner_id'] is None for r in case.journal.status()['runs']))
