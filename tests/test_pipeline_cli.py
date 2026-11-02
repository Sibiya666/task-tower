import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import uuid
import threading
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch

from task_tower.pipeline_journal import PipelineJournal


class ControllerTests(unittest.TestCase):
    def test_singleton_health_and_release(self):
        with tempfile.TemporaryDirectory() as directory:
            journal=PipelineJournal(Path(directory).resolve()/'pipeline.db')
            owner=str(uuid.uuid4())
            journal.claim_controller(owner,'a'*64)
            with self.assertRaises(ValueError):
                journal.claim_controller(str(uuid.uuid4()),'a'*64)
            journal.controller_tick(owner,dict(ticks=1,read_failures=0,workers=0,dispatcher=0))
            self.assertEqual(journal.controller_health()['health']['ticks'],1)
            with self.assertRaises(ValueError):journal.release_controller(str(uuid.uuid4()))
            journal.release_controller(owner)
            self.assertTrue(journal.controller_health()['health']['stopped'])
            replacement=str(uuid.uuid4());journal.claim_controller(replacement,'b'*64)
            self.assertFalse(journal.controller_health()['health']['stopped'])

    def test_health_read_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'missing.db';journal=PipelineJournal(path)
            self.assertIsNone(journal.controller_health())
            self.assertFalse(path.exists())

    def test_cli_route_and_required_arguments(self):
        from task_tower import pipeline
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as result:
            pipeline.main(['work'])
        self.assertEqual(result.exception.code,2)

    def test_work_exit_codes_distinguish_uncertainty_from_parked(self):
        from task_tower import pipeline
        args=['work','--connections',str(Path('C.json').resolve()),'--journal',str(Path('J.db').resolve()),'--config',str(Path('P.json').resolve()),'--executor-config',str(Path('E.json').resolve()),'--once']
        def runtime(parsed):
            parsed._connections_bytes=b'fixed'
            return [],object(),{}
        for report,expected in ((dict(status='unknown',reason='cleanup_unknown'),1),(dict(status='executing',reason=None),1),(dict(status='publishing',reason=None),1),(dict(status='needs_input',reason='environment_unavailable'),0)):
            with patch('task_tower.pipeline._runtime',side_effect=runtime),patch('task_tower.pipeline.work',return_value=report),patch.object(Path,'read_bytes',return_value=b'fixed'),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pipeline.main(args),expected)

    def test_live_and_unprovable_controller_never_stolen(self):
        with tempfile.TemporaryDirectory() as directory:
            journal=PipelineJournal(Path(directory).resolve()/'pipeline.db');owner=str(uuid.uuid4())
            journal.claim_controller(owner,'a'*64)
            with patch('task_tower.pipeline_journal._dead',return_value=False):
                with self.assertRaises(ValueError):journal.claim_controller(str(uuid.uuid4()),'b'*64)
            with patch('task_tower.pipeline_journal._dead',return_value=True):
                replacement=str(uuid.uuid4());journal.claim_controller(replacement,'b'*64)
            self.assertEqual(journal.controller_health()['owner_id'],replacement)

    def test_invalid_health_has_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            journal=PipelineJournal(Path(directory).resolve()/'pipeline.db');owner=str(uuid.uuid4());journal.claim_controller(owner,'a'*64)
            before=journal.controller_health()
            for health in (dict(ticks=True,read_failures=0,workers=0,dispatcher=0),dict(ticks=1,read_failures=0,workers=3,dispatcher=0),dict(arbitrary='private')):
                with self.assertRaises(ValueError):journal.controller_tick(owner,health)
                self.assertEqual(journal.controller_health(),before)

    def test_same_repository_actions_serialize_but_other_repository_claims(self):
        from tests.test_pipeline_journal import request,policy
        with tempfile.TemporaryDirectory() as directory:
            journal=PipelineJournal(Path(directory).resolve()/'pipeline.db')
            journal.submit(request(1),policy(['first']))
            journal.submit(request(2),policy(['second']))
            journal.submit(dict(request(3),repository='other/repository'),policy(['third']))
            first=journal.claim(str(uuid.uuid4()),2)
            second=journal.claim(str(uuid.uuid4()),2)
            self.assertNotEqual(first['repository'],second['repository'])

    def test_host_budget_is_own_run_bound_and_monotonic(self):
        from task_tower import pipeline
        now=datetime.now(timezone.utc)
        unrelated=dict(owner_id='other',state='executing',deadline_at=(now-timedelta(seconds=1)).isoformat())
        journal=SimpleNamespace(status=lambda:dict(runs=[unrelated]))
        self.assertEqual(pipeline._remaining(dict(task_timeout_seconds=60),journal),60)
        host=object.__new__(pipeline._Host);host.owner='own';host.stop=threading.Event();host._budget_deadline=None
        run=dict(owner_id='own',cancel_requested=False,deadline_at=(now+timedelta(seconds=30)).isoformat(),updated_at=now.isoformat())
        host.journal=SimpleNamespace(status=lambda:dict(runs=[run]),operation_deadline=lambda deadline:contextlib.nullcontext())
        with patch('task_tower.pipeline.time.monotonic',side_effect=[100,100,131,131]):
            self.assertFalse(host.cancelled());self.assertTrue(host.cancelled())

    def test_ready_cancel_requires_positive_dead_owner_and_saved_cleanup(self):
        from tests.test_pipeline_journal import ReadyResumeTests,uid
        fixture=ReadyResumeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        owner=uid()
        with fixture.journal.owner(owner):
            run=fixture.ready(owner)
            fixture.journal.cancel(run['run_id'])
            self.assertEqual(fixture.journal.status(run['run_id'])['state'],'ready')
            # The actual live matching owner can cooperate without replaying work.
            current=fixture.journal.status(run['run_id'])
            fixture.journal.record(run['run_id'],owner,{k:current[k] for k in ('state','stage','generation','input_sha256')},dict(state='cancelled',reason='cancelled',evidence=dict(cleanup_confirmed=True)))
            self.assertEqual(fixture.journal.status(run['run_id'])['state'],'cancelled')

    def test_cancel_does_not_release_unresolved_or_unknown_work(self):
        from tests.test_pipeline_journal import ReadyResumeTests,uid
        fixture=ReadyResumeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        owner=uid()
        with fixture.journal.owner(owner):run=fixture.ready(owner)
        current=fixture.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='reviewing'))
        fixture.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=current['manifest'],artifact_names={}))
        with patch('task_tower.pipeline_journal._dead',return_value=True):
            fixture.journal.cancel(run['run_id']);fixture.journal.recover()
        self.assertEqual(fixture.journal.status(run['run_id'])['state'],'unknown')

    def test_ready_handoff_rejects_clock_rollback_before_owner_rewrite(self):
        from tests.test_pipeline_journal import ReadyResumeTests,uid
        fixture=ReadyResumeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        owner=uid()
        with fixture.journal.owner(owner):run=fixture.ready(owner)
        before=fixture.journal.status(run['run_id']);history=fixture.journal.history(run['run_id'])
        earlier=(datetime.fromisoformat(before['updated_at'])-timedelta(seconds=1)).isoformat()
        with fixture.journal.owner(uid()) as replacement,patch('task_tower.pipeline_journal._dead',return_value=True),patch('task_tower.pipeline_journal._now',return_value=earlier):
            with self.assertRaises(ValueError):fixture.journal.claim(replacement,1)
        self.assertEqual(fixture.journal.status(run['run_id']),before)
        self.assertEqual(fixture.journal.history(run['run_id']),history)


if __name__=='__main__':unittest.main()
