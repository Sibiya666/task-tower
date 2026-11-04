"""Metadata survives revoked role files; it never constructs execution context."""
import contextlib
import io
import json
import unittest
import sys
import uuid
from unittest.mock import patch
from tests import test_pr_context as fixture
from tests.test_pr_journal import binding
from task_tower.pr_journal import PRJournal


class MetadataCLITests(unittest.TestCase):
    setUp=fixture.ContextFactoryTests.setUp
    write=staticmethod(fixture.ContextFactoryTests.write)

    def call(self,operation,*args):
        from task_tower.pr_worker_cli import main
        output=io.StringIO()
        argv=[operation,'--connections',str(self.connections),'--config',str(self.policy),'--journal',str(self.journal),*args]
        with contextlib.redirect_stdout(output):code=main(argv)
        return code,json.loads(output.getvalue())

    def test_status_and_inspection_survive_deleted_executable_inputs_without_pipeline_locator(self):
        j=PRJournal(self.journal);j.admit(binding())
        before=self.journal.read_bytes()
        self.policy.unlink();self.executor.unlink();self.pipeline.unlink();(self.pins/'SKILL.md').unlink()
        with patch('task_tower.pr_context.PRHostContext.from_inputs',side_effect=AssertionError('Executable loader')):
            code,result=self.call('status')
            self.assertEqual(code,0);self.assertEqual(result['tasks'][0]['pr_number'],44)
            code,result=self.call('reconcile','--repository','owner/repo','--pr','44','--inspect')
            self.assertEqual(code,0);self.assertEqual(result['effects'],[])
        self.assertEqual(before,self.journal.read_bytes())
        self.assertNotIn(str(self.root),json.dumps(result))

    def test_cancel_is_metadata_only_and_keeps_original_identity(self):
        j=PRJournal(self.journal);original=j.admit(binding())
        self.executor.unlink();self.policy.unlink()
        code,result=self.call('cancel','--repository','owner/repo','--pr','44')
        self.assertEqual(code,0);self.assertEqual(result['status'],'cancelled')
        current=j.get('owner/repo',44)
        self.assertTrue(current['cancel_requested'])
        for key in ('input_sha256','admitted_utc','deadline_utc','head_sha','base_sha'):
            self.assertEqual(original[key],current[key])

    def test_missing_status_never_creates_journal_or_private_artifacts(self):
        before={p.name for p in self.root.iterdir()}
        code,result=self.call('status')
        self.assertEqual(code,0);self.assertEqual(result['tasks'],[])
        self.assertEqual(before,{p.name for p in self.root.iterdir()})

    def test_cancel_of_owned_preparation_exposes_the_retained_cancellation_flag(self):
        journal=PRJournal(self.journal);owner=str(uuid.uuid4())
        with journal.owner(owner):
            row=journal.admit(binding())
            journal.transition('owner/repo',44,owner,
                dict(state='discovered',input_sha256=row['input_sha256']),dict(state='validating'))
        code,result=self.call('cancel','--repository','owner/repo','--pr','44')
        self.assertEqual(code,0);self.assertEqual(result['status'],'validating')
        self.assertTrue(result['cancel_requested'])
        code,status=self.call('status')
        self.assertEqual(code,0);self.assertTrue(status['tasks'][0]['cancel_requested'])

    def test_work_once_requires_the_actual_explicit_pipeline_locator_without_creating_state(self):
        code,result=self.call('work','--once')
        self.assertEqual(code,2)
        self.assertEqual(result['reason'],'pr_execution_unverified')
        self.assertFalse(self.journal.exists())

    def test_actual_once_reports_source_refusal_and_retires_its_real_owner(self):
        from task_tower.processes import run_command as actual_run
        script="import sys\nfrom task_tower import pr_source\npr_source.resolve_token=lambda:None\ndef unavailable(*args):raise OSError('HTTP fixture')\npr_source._transport=unavailable\nfrom task_tower._pr_host import main\nraise SystemExit(main(sys.argv[1:]))\n"
        launches=[]
        def controlled(argv,*args,**kwargs):
            self.assertEqual(argv[1:4],['-B','-m','task_tower._pr_host']);launches.append(True)
            return actual_run([argv[0],'-B','-c',script,*argv[4:]],*args,**kwargs)
        source_before=self.source.read_bytes()
        with patch('task_tower.processes.run_command',side_effect=controlled):
            code,result=self.call('work','--once','--pipeline-config',str(self.pipeline))
        self.assertEqual(launches,[True]);self.assertEqual(code,1)
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['report']['reason'],'pr_step_unverified')
        self.assertTrue(result['owner_retired']);self.assertTrue(result['cleanup_confirmed'])
        self.assertNotIn(str(self.root),json.dumps(result))
        self.assertEqual(source_before,self.source.read_bytes())
        journal=PRJournal(self.journal)
        self.assertEqual(journal.rows(),[])
        with journal._db() as db:self.assertEqual([r['status'] for r in db.execute('SELECT status FROM owners')],['retired'])
