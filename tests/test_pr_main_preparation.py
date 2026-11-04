"""Real stage/review/merge records and Git objects; only HTTP is replaced."""
import copy
import json
import io
import zipfile
import sys
import time
import os
import uuid
from contextlib import nullcontext
from pathlib import Path
import unittest
from unittest.mock import patch
from task_tower.pr_policy import canonical
from tests import test_pr_publication_effects as publication
from tests import test_github_source as github_fixture


class MainPreparationTests(publication._PublicationFixture,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current=publication.gate_fixture.record_fixtures.preparation_fixture.current_fixture
        original=current.installed_load
        def install(f):
            script=f.root/'actual-main-reviewer.py'
            script.write_text("import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args();r=json.loads(pathlib.Path(a.request).read_text());v=dict(task_id=r['task']['id'],commit=r['bundle']['merge_commit'],verdict='approve',summary='Actual independent main reviewer fixture.',findings=[]);pathlib.Path(a.result).write_text(json.dumps(v))\n",encoding='utf-8')
            profile=copy.deepcopy(f.profile)
            profile.update(argv=[str(Path(sys.executable).resolve()),str(script)],max_attempts=1,runs_dir=str(f.root/'actual-main-review-runs'))
            f.executor['profiles']['main-review']=profile
            return original(f)
        with patch.object(current,'installed_load',side_effect=install):
            publication._PublicationFixture.setUpClass.__func__(cls)

    def context(self):
        value=json.loads(self.policy.read_text())
        value['projects'][0]['tasks'][0]['postmerge_profile']='main-review'
        self.policy.write_text(json.dumps(value),encoding='utf-8')
        return publication._PublicationFixture.context(self)

    def test_actual_main_review_and_closure_never_repeat_lost_writes(self):
        effects,store=self.publication();source=effects.source;backing=source.transport
        repository=self.request['repository'];number=self.request['pr_number']
        checkout=Path(self.host.stage_run['worktree'])
        git=lambda *args:self.host.f.real_git(checkout,*args).decode().strip()
        head=self.request['head_sha'];base=self.request['base_sha']
        tree=git('rev-parse',head+'^{tree}')
        merge=git('-c','user.name=Fixture','-c','user.email=f@example.invalid','commit-tree',tree,'-p',base,'-p',head,'-m','actual merge fixture')
        done=[];puts=[];pr=copy.deepcopy(self.fresh['snapshot']['pr'])
        pr.update(state='closed',merged=True,merge_commit_sha=merge,merged_at='2026-11-01T12:00:00Z',merged_by=dict(login=self.fresh['task']['publisher_account']))
        pr['base']['sha']=merge
        prefix='https://api.github.com/repos/'+repository
        def transport(method,url,headers,body,timeout,max_bytes):
            if method=='PUT':
                puts.append(url);done.append(True)
                value=dict(status='merged',details=dict(message='Merged.',sha=merge));code=200
            elif done and method=='GET' and url==prefix+'/pulls/'+str(number):value=pr;code=200
            elif done and method=='GET' and url==prefix+'/git/commits/'+merge:
                value=dict(sha=merge,parents=[dict(sha=base),dict(sha=head)]);code=200
            elif done and method=='GET' and url==prefix+'/git/ref/heads/main':value=dict(object=dict(sha=merge));code=200
            else:return backing(method,url,headers,body,timeout,max_bytes)
            return dict(status=code,headers={},body=canonical(value).encode())
        source.transport=transport
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            effects.publish(self.receipt);effects.publish(self.receipt)
            self.pr.transition(repository,number,self.owner_id,dict(state='publishing_acceptance',input_sha256=self.input_sha),dict(state='accepted'))
            effects.request_merge(self.receipt)
            effects.observe_merge()
        self.assertEqual(self.pr.get(repository,number)['state'],'awaiting_main')
        connection_repository=self.ctx._fresh_inputs()['connections'][0].repository
        main_pr=copy.deepcopy(pr)
        for side in ('head','base'):main_pr[side]['repo']['full_name']=connection_repository
        def change(p,r,e):
            from task_tower.merge_events import build_merge_event
            p.clear();p.update(main_pr)
            r['head_sha']=head
            r['repository']['full_name']=connection_repository
            e.clear();e.update(build_merge_event(dict(action='closed',repository=dict(full_name=connection_repository),pull_request=p),connection_repository,'linux','passed',12,2))
        github=github_fixture.GitHubSourceTests().source(change)
        github.repository=connection_repository
        original_http=github.transport;all_platforms=[]
        def main_http(url,headers,limit):
            if '/artifacts?' in url:
                value=json.loads(original_http(url,headers,limit))
                artifact=value['artifacts'][0];artifact['workflow_run']['head_sha']=head
                if all_platforms:
                    value['artifacts']=[dict(artifact,id=22+i,name='task-tower-merge-7-'+platform) for i,platform in enumerate(('linux','macos','windows'))]
                return json.dumps(value).encode()
            if '/zip' in url and all_platforms:
                from task_tower.merge_events import build_merge_event
                platform=('linux','macos','windows')[int(url.split('/')[-2])-22]
                event=build_merge_event(dict(action='closed',repository=dict(full_name=connection_repository),pull_request=main_pr),connection_repository,platform,'passed',12,2)
                stream=io.BytesIO()
                with zipfile.ZipFile(stream,'w') as archive:archive.writestr('merge-event.json',json.dumps(event))
                return stream.getvalue()
            return original_http(url,headers,limit)
        github.transport=main_http
        from task_tower import pr_main
        self.assertTrue(callable(getattr(pr_main,'prepare_main',None)),'Missing genuine main preparation')
        def fetch(mirror,url,b,m,logs):
            from task_tower.pr_source import _git
            self.assertEqual((b,m),(base,merge))
            _git(mirror,['-c','protocol.file.allow=always','fetch','--no-tags','--no-recurse-submodules','--',str(checkout),b,m],logs)
        task=copy.deepcopy(self.fresh['task']);task['required_platforms']=['linux']
        # Caller convenience changes never override the actual private policy.
        # Its fixture policy requires all three platforms, so incomplete CI is
        # refused before creating the private mirror or launching a role.
        before=self.pr.path.read_bytes()
        with patch('task_tower.pr_main._fetch',side_effect=fetch):
            self.assertIsNone(pr_main.prepare_main(self.ctx,source,github,self.pr,task,self.owner_id))
        self.assertEqual(before,self.pr.path.read_bytes())
        all_platforms.append(True)
        from task_tower.pr_worker import Controller,step
        controller=Controller.from_context(self.ctx,self.pr,self.owner_id,sources={repository:source},main_sources={repository:github})
        with patch('task_tower.pr_main._fetch',side_effect=fetch):
            report=step(controller.config,self.pr,owner_id=self.owner_id)
        self.assertEqual(report['action'],'main_prepared',report)
        self.assertEqual(report['status'],'awaiting_postmerge')
        prepared=controller._mains[(repository,number)]
        self.assertIsInstance(prepared,pr_main.MainPreparation)
        self.assertEqual(prepared.bundle['merge_commit'],merge)
        from task_tower import tasks
        card=tasks.load_task(prepared.card)
        self.assertEqual(card['status'],'awaiting_merge')
        self.assertEqual(card['id'],self.request['task_id'])
        self.assertEqual(set(card['stages']),{'spec','development','test','postmerge'})
        self.assertEqual(self.pr.get(repository,number)['state'],'awaiting_postmerge')
        self.assertEqual(len(puts),1);self.assertEqual(len(store['posts']),2)
        self.assertFalse(any(e['kind']=='postmerge_review' for e in self.pr.effects(repository,number)))
        def refresh(worker):
            from task_tower.pr_source import _git
            _git(worker.project,['-c','protocol.file.allow=always','fetch','--no-tags','--no-recurse-submodules','--',str(checkout),merge+':refs/remotes/origin/main'],prepared.mirror.parent/'logs')
            if getattr(self,'cancel_during_review_reads',False):self.pr.cancel(repository,number)
        from task_tower import reviewer
        telemetry_fault=getattr(self,'fail_telemetry_cleanup',False)
        if telemetry_fault:
            from task_tower.pr_supervision import PRProgress,_Wire
            namespace=Path(self.ctx.private_input_provenance['artifact_namespace'])
            descriptor=os.open(namespace/'test-control.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            self.addCleanup(os.close,descriptor)
            self.ctx._lifecycle=PRProgress.from_controller(controller,_Wire(descriptor,str(uuid.uuid4()),self.owner_id),namespace/'test-stop')
            self.ctx._lifecycle.begin(repository,number)
        returned=[];actual_run=reviewer.run_command
        def captured(*args,**kwargs):
            value=actual_run(*args,**kwargs);returned.append(copy.deepcopy(value));return value
        with patch('task_tower.postmerge_worker.Worker._refresh',refresh),patch('task_tower.reviewer.run_command',side_effect=captured) as launches:
            fault=patch('task_tower.pr_supervision.PRProgress.end_role',side_effect=OSError('Controlled channel failure')) if telemetry_fault else nullcontext()
            with fault:
                try:report=controller._advance(self.fresh['task'])[0]
                except ValueError:
                    if not getattr(self,'cancel_during_review_reads',False) and not telemetry_fault:raise
                    report=dict(status='needs_input')
        if telemetry_fault:
            self.assertEqual(launches.call_count,1)
            effect=[e for e in self.pr.effects(repository,number) if e['kind']=='postmerge_review'][0]
            path=prepared.mirror/'.task-tower'/'bound-output'/effect['effect_id']/'process.json'
            self.assertTrue(path.is_file(),'Returned execution evidence lost before fallible telemetry')
            self.assertEqual(json.loads(path.read_text())['process'],returned[0])
            self.assertNotEqual(effect['status'],'confirmed');self.assertIsNotNone(self.pr.barrier(repository))
            return
        if getattr(self,'cancel_during_review_reads',False):
            self.assertEqual(launches.call_count,0,'Cancelled original task must not launch a reviewer')
            self.assertNotEqual(report['status'],'awaiting_closure')
            self.assertIsNotNone(self.pr.barrier(repository))
            return
        self.assertEqual(report['action'],'postmerge_review',report)
        self.assertEqual(report['status'],'awaiting_closure')
        post=[e for e in self.pr.effects(repository,number) if e['kind']=='postmerge_review']
        self.assertEqual(len(post),1)
        self.assertEqual(post[0]['status'],'confirmed')
        self.assertNotEqual(post[0]['payload']['reviewer_instance_id'],self.receipt['reviewer_instance_id'])
        self.assertGreater(post[0]['observation']['process']['pid'],0)
        self.assertEqual(len(puts),1);self.assertEqual(len(store['posts']),2)
        issue=copy.deepcopy(self.fresh['snapshot']['issue_payload'])
        if getattr(self,'changed_criteria',False):issue['title']+=' changed after independent main review'
        comments=[];writes=[];lost={'POST':True,'PATCH':True}
        def publication_http(method,url,headers,payload,limit):
            self.assertEqual(url[:len(prefix)].casefold(),prefix.casefold())
            path=url[len(prefix):]
            if method=='GET' and path=='/issues/16':value=issue
            elif method=='GET' and path.startswith('/issues/16/comments?'):value=comments
            elif method=='GET' and path.startswith('/compare/'):value=dict(status='identical')
            elif method=='POST' and path=='/issues/16/comments':
                writes.append(method)
                value=dict(id=7001,body=payload['body'],user=dict(login=self.fresh['task']['publisher_account']))
                comments.append(value)
                if lost[method]:lost[method]=False;raise OSError('Lost actual comment response')
            elif method=='PATCH' and path=='/issues/16':
                self.assertEqual(payload,dict(state='closed',state_reason='completed'))
                writes.append(method);issue.update(payload);value=issue
                if lost[method]:lost[method]=False;raise OSError('Lost actual closure response')
            else:raise AssertionError((method,path))
            return json.dumps(value).encode()
        original_current=pr_main._prepared_current
        injected=[]
        def after_current(*args,**kwargs):
            result=original_current(*args,**kwargs)
            if getattr(self,'late_fault',None) and not injected and any(
                    e['kind']==self.revoke_on and e['status']=='intent' for e in self.pr.effects(repository,number)):
                injected.append(True)
                if self.late_fault=='cancel':self.pr.cancel(repository,number)
                else:self.pr._clock_limits[(repository,number)]=time.monotonic()-1
            return result
        with patch('task_tower.github_tasks._transport',side_effect=publication_http),patch('task_tower.github_tasks.resolve_token',return_value=None),patch('task_tower.pr_main._prepared_current',side_effect=after_current):
            original_begin=self.pr.begin_effect
            def guarded_begin(*args,**kwargs):
                effect=original_begin(*args,**kwargs)
                if effect['kind']==getattr(self,'revoke_on',None) and not getattr(self,'late_fault',None):
                    self.policy.write_bytes(self.policy.read_bytes()+b' ')
                return effect
            self.pr.begin_effect=guarded_begin
            for _ in range(8):
                before_writes=len(writes)
                report=step(controller.config,self.pr,owner_id=self.owner_id)
                self.assertLessEqual(len(writes)-before_writes,1)
                if report['status']=='completed':break
                if getattr(self,'changed_criteria',False) and report['status']=='needs_input':break
                if getattr(self,'revoke_on',None) and report['status'] in ('needs_input','unknown'):break
            if getattr(self,'revoke_on',None):
                if getattr(self,'late_fault',None):self.assertEqual(injected,[True])
                expected=[] if self.revoke_on=='comment_post' else ['POST']
                self.assertEqual(writes,expected)
                self.assertNotEqual(report['status'],'completed')
                effects=[e for e in self.pr.effects(repository,number) if e['kind']==self.revoke_on]
                self.assertEqual(len(effects),1)
                self.assertIn(effects[0]['status'],('intent','unknown'))
                self.assertIsNotNone(self.pr.barrier(repository))
                return
            if getattr(self,'changed_criteria',False):
                self.assertNotEqual(report['status'],'completed',report)
                self.assertEqual(writes,[])
                self.assertIsNotNone(self.pr.barrier(repository))
                return
            self.assertEqual(report['status'],'completed',report)
            step(controller.config,self.pr,owner_id=self.owner_id)
        self.assertEqual(writes,['POST','PATCH'])
        self.assertEqual(issue['state'],'closed');self.assertEqual(issue['state_reason'],'completed')
        self.assertIsNone(self.pr.barrier(repository))
        self.assertEqual(self.pr.get(repository,number)['postmerge_attempts'],1)
        if getattr(self,'inspect_original_event',False):
            from task_tower.pr_worker_cli import main
            from contextlib import redirect_stdout
            output=io.StringIO();inputs=self.ctx._inputs
            before=self.pr.path.read_bytes()
            argv=['reconcile','--inspect','--connections',str(inputs.connections_path),
                '--config',str(inputs.policy_path),'--journal',str(inputs.journal_path),
                '--repository',repository,'--pr',str(number)]
            with patch('task_tower.github_source._http_get',side_effect=main_http),patch('task_tower.github_source.resolve_token',return_value=None),redirect_stdout(output):
                code=main(argv)
            self.assertEqual(code,0)
            inspected=json.loads(output.getvalue())
            self.assertEqual(inspected['recovery']['required_action'],'fresh_acceptance_required')
            self.assertEqual(len(inspected['recovery']['events']),3)
            self.assertEqual(before,self.pr.path.read_bytes())


class ChangedCriteriaMainTests(MainPreparationTests):
    changed_criteria=True


class OriginalEventInspectionMainTests(MainPreparationTests):
    inspect_original_event=True


class CommentIntentRevocationMainTests(MainPreparationTests):
    revoke_on='comment_post'


class CloseIntentRevocationMainTests(MainPreparationTests):
    revoke_on='issue_close'


class CommentLateCancellationMainTests(MainPreparationTests):
    revoke_on='comment_post'
    late_fault='cancel'


class CloseLateDeadlineMainTests(MainPreparationTests):
    revoke_on='issue_close'
    late_fault='deadline'


class ReviewerLateCancellationMainTests(MainPreparationTests):
    cancel_during_review_reads=True


class ReviewerTelemetryFailureMainTests(MainPreparationTests):
    fail_telemetry_cleanup=True


class TelemetryMainChainTests(MainPreparationTests):
    """Real model/closure path and typed channel; observer is in-process."""
    def test_actual_main_review_and_closure_never_repeat_lost_writes(self):
        from task_tower.pr_worker import Controller
        from task_tower.pr_supervision import PRProgress,PRMonitor,_Wire
        factory=Controller.from_context.__func__;advance=Controller._advance;channels=[]
        def constructed(cls,*args,**kwargs):
            controller=factory(cls,*args,**kwargs)
            namespace=Path(controller.context.private_input_provenance['artifact_namespace'])
            path=namespace/('telemetry-'+str(uuid.uuid4())+'.jsonl')
            descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            self.addCleanup(os.close,descriptor)
            reader=path.open('rb');self.addCleanup(reader.close)
            monitor=PRMonitor.from_context(controller.context,owner_id=controller.owner_id);monitor.started(os.getpid())
            wire=_Wire(descriptor,monitor.session_id,controller.owner_id);send=wire.send
            def observed(event,**fields):
                send(event,**fields)
                data=reader.read(65536)
                if data:monitor.feed(data)
                self.assertIsNone(monitor.reason)
            wire.send=observed;wire.send('hello')
            controller.context._lifecycle=PRProgress.from_controller(controller,wire,namespace/'unused-stop')
            channels.append((wire,monitor));return controller
        def monitored(controller,task):
            progress=controller.context._lifecycle
            own_phase=progress._phase is None
            try:
                if own_phase:progress.begin(task['repository'],task['pr_number'])
                row=controller.journal.get(task['repository'],task['pr_number'])
                reference=(task['repository'].casefold(),task['pr_number'])
                if row is not None and row['owner_id']==controller.owner_id and reference not in progress._known:
                    progress.admitted(*reference)
                return advance(controller,task)
            finally:
                if own_phase:progress.end()
        with patch.object(Controller,'from_context',classmethod(constructed)),patch.object(Controller,'_advance',monitored):
            super().test_actual_main_review_and_closure_never_repeat_lost_writes()
        self.assertTrue(channels)
        for wire,monitor in channels:
            wire.send('end');monitor.finished(0)
            self.assertIsNone(monitor.reason)
