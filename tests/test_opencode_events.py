"""Synthetic V2 CLI projections, source qualified but never native traces.

Source: anomalyco/opencode@9bbb8ce18c80f099e0e448775f59d965ead40a21
packages/cli/src/run/noninteractive.ts and schema/src/token-usage.ts.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
import subprocess
from unittest.mock import patch

from task_tower import opencode_adapter as adapter
from task_tower.executor_harness import result_schema
from task_tower.executor_profiles import profile_fingerprint


def event(kind,message='msg_one',part_id=None,**extra):
    types={'step_start':'step-start','step_finish':'step-finish','text':'text','tool_use':'tool'}
    part=dict(sessionID='ses_fixture',messageID=message,type=types[kind])
    if kind=='tool_use':
        part.update(partID=part_id or 'prt_tool',id='call_one',tool='fixture',state=dict(status='completed',input={},output='private tool output',title='fixture',metadata={},time=dict(start=1,end=2)))
    else:part['id']=part_id or 'prt_'+kind
    if kind=='text':part.update(text='private text \U0001f9ea',time=dict(start=1,end=2))
    if kind=='step_finish':part.update(reason='stop',cost=0,tokens=dict(input=1,output=1,reasoning=0,cache=dict(read=0,write=0)))
    part.update(extra)
    return dict(type=kind,timestamp=2,sessionID='ses_fixture',part=part)


class EventTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.path=self.root/'stdout.log'
        self.events=[event('step_start'),event('text'),event('step_finish')]

    def parse(self,events=None,data=None,**overrides):
        if data is None:data=b''.join((json.dumps(row,ensure_ascii=False)+'\n').encode() for row in (self.events if events is None else events))
        self.path.write_bytes(data)
        process=dict(status='passed',exit_code=0,started=True,cleanup_confirmed=True,stdout_bytes=len(data),stdout_captured_bytes=len(data),
            stdout_sha256=hashlib.sha256(data).hexdigest(),stdout_truncated=False,stdout_tail_unknown=False,stderr_tail_unknown=False)
        process.update(overrides)
        return adapter.parse_opencode_events(self.path,process=process)

    def test_v2_live_and_reconciled_stop(self):
        result=self.parse();self.assertTrue(result['valid'],result)
        self.assertEqual(result['session_id'],'ses_fixture');self.assertEqual(result['event_count'],3)
        self.assertTrue(result['terminal_stop']);self.assertNotIn('private',json.dumps(result))
        self.assertEqual(set(result),{'valid','session_id','event_count','terminal_stop','error_count','evidence_sha256'})

    def test_source_attributed_synthetic_projection_fixture(self):
        fixture=Path(__file__).parent/'fixtures'/'opencode-v2'/'live-reconciled-stop.synthetic.jsonl'
        self.assertTrue(self.parse(data=fixture.read_bytes())['valid'])

    def test_projected_text_after_same_message_stop(self):
        suffix=event('text',part_id='prt_projected_suffix');suffix['timestamp']=0
        self.assertTrue(self.parse([*self.events,suffix])['valid'])

    def test_new_unfinished_step_after_stop_fails(self):
        self.assertFalse(self.parse([*self.events,event('step_start','msg_new',part_id='prt_new')])['valid'])
        self.assertTrue(self.parse([*self.events,event('step_start','msg_new',part_id='prt_new'),event('step_finish','msg_new',part_id='prt_end_new')])['valid'])

    def test_outer_nested_session_mismatch(self):
        for where in ('outer','nested'):
            rows=copy.deepcopy(self.events)
            if where=='outer':rows[1]['sessionID']='ses_foreign'
            else:rows[1]['part']['sessionID']='ses_foreign'
            with self.subTest(where=where):self.assertFalse(self.parse(rows)['valid'])

    def test_wrong_type_noise_duplicate_keys_invalid_utf8(self):
        for data in (b'noise\n',b'[]\n',b'{"type":"text","type":"error"}\n',b'\xff\n',b'{}\n',b'{"x":NaN}\n'):
            with self.subTest(data=data):self.assertFalse(self.parse(data=data)['valid'])
        for field,value in [('timestamp',True),('sessionID',3),('type','reasoning')]:
            rows=copy.deepcopy(self.events);rows[0][field]=value
            with self.subTest(field=field):self.assertFalse(self.parse(rows)['valid'])

    def test_conflicting_terminal_duplicate(self):
        self.assertTrue(self.parse([*self.events,copy.deepcopy(self.events[-1])])['valid'])
        conflict=copy.deepcopy(self.events[-1]);conflict['part']['reason']='length'
        self.assertFalse(self.parse([*self.events,conflict])['valid'])

    def test_error_and_tool_error_prevent_completion(self):
        err=dict(type='error',timestamp=1,sessionID='',error=dict(type='fixture',message='private credentialless error'))
        self.assertFalse(self.parse([err,*self.events])['valid'])
        tool=event('tool_use');self.assertTrue(self.parse([self.events[0],tool,*self.events[1:]])['valid'])
        tool['part']['state']=dict(status='error',input={},error='private error',metadata={},time=dict(start=1,end=2))
        result=self.parse([self.events[0],tool,*self.events[1:]])
        self.assertFalse(result['valid']);self.assertGreater(result['error_count'],0)

    def test_missing_nonstop_and_unowned_projection(self):
        self.assertFalse(self.parse(self.events[:-1])['valid'])
        for reason in ('length','tool-calls','error','unknown'):
            rows=copy.deepcopy(self.events);rows[-1]['part']['reason']=reason
            with self.subTest(reason=reason):self.assertFalse(self.parse(rows)['valid'])
        self.assertFalse(self.parse([*self.events,event('text','msg_unowned',part_id='prt_unowned')])['valid'])

    def test_stdout_unknown_tail_caps_and_process_proof(self):
        for change in (dict(stdout_truncated=True),dict(stdout_tail_unknown=True),dict(stdout_bytes=67108865),dict(exit_code=True),dict(cleanup_confirmed=False),dict(status='cancelled'),dict(stdout_sha256='0'*64)):
            with self.subTest(change=change):self.assertFalse(self.parse(**change)['valid'])
        self.assertFalse(self.parse(data=b' '*1048577+b'\n')['valid'])

    def test_tool_call_id_is_opaque_and_terminal_identity_cannot_conflict(self):
        tool=event('tool_use');tool['part']['id']='provider:opaque/call'
        self.assertTrue(self.parse([self.events[0],tool,*self.events[1:]])['valid'])
        conflict=copy.deepcopy(tool);conflict['part']['partID']='prt_other';conflict['part']['state']['output']='changed terminal'
        self.assertFalse(self.parse([self.events[0],tool,conflict,*self.events[1:]])['valid'])

    def test_projected_tool_and_message_ids_are_opaque_utf8_scalar_values(self):
        message='msg_opaque:\u03b1/step'
        start=event('step_start',message,part_id='prt_start:\u03b1/one')
        tool=event('tool_use',message,part_id='prt_opaque_tool-provider:call/\u5de5\u5177');tool['part']['id']='provider:call/\u5de5\u5177'
        finish=event('step_finish',message,part_id='prt_finish:\u03b1/two')
        self.assertTrue(self.parse([start,tool,finish,copy.deepcopy(tool)])['valid'])
        conflict=copy.deepcopy(tool);conflict['part']['state']['output']='different'
        self.assertFalse(self.parse([start,tool,finish,conflict])['valid'])

    def test_opaque_id_length_scalar_and_session_alphabet_countercases(self):
        for field in ('id','messageID'):
            rows=copy.deepcopy(self.events);value='\u03b1'*256
            if field=='id':rows[1]['part'][field]=value
            else:
                for row in rows:row['part'][field]=value
            self.assertTrue(self.parse(rows)['valid'])
            for bad in ('\u03b1'*257,'\ud800',''):
                mutated=copy.deepcopy(rows);mutated[1]['part'][field]=bad
                data=b''.join((json.dumps(row,ensure_ascii=True)+'\n').encode() for row in mutated)
                with self.subTest(field=field,bad_length=len(bad)):self.assertFalse(self.parse(data=data)['valid'])
        for row in self.events:
            row['sessionID']='ses_bad:\u03b1';row['part']['sessionID']=row['sessionID']
        self.assertFalse(self.parse()['valid'])

    def test_same_part_identity_cannot_change_event_kind(self):
        rows=copy.deepcopy(self.events);rows[1]['part']['id']=rows[0]['part']['id']
        self.assertFalse(self.parse(rows)['valid'])

    def test_known_field_types_and_identifier_boundaries(self):
        self.events[0]['sessionID']='ses_'+'a'*252
        for row in self.events:row.update(sessionID=self.events[0]['sessionID']);row['part']['sessionID']=row['sessionID']
        self.assertTrue(self.parse()['valid'])
        self.events[0]['sessionID']+='a';self.assertFalse(self.parse()['valid'])
        for location,key,value in [('part','text',4),('tokens','input',True),('cache','read','1'),('part','snapshot',[]),('event','timestamp',float('inf'))]:
            rows=[event('step_start'),event('text'),event('step_finish')]
            target=rows[1]['part'] if key=='text' else rows[-1]['part']
            if location=='tokens':target=target['tokens']
            elif location=='cache':target=target['tokens']['cache']
            elif location=='event':target=rows[0]
            target[key]=value
            with self.subTest(key=key):self.assertFalse(self.parse(rows)['valid'])

    def test_line_and_event_count_exact_boundaries(self):
        text=event('text');text['part']['text']=''
        overhead=len((json.dumps(text,ensure_ascii=False)+'\n').encode())
        text['part']['text']='x'*(1048576-overhead)
        self.assertTrue(self.parse([self.events[0],text,self.events[-1]])['valid'])
        text['part']['text']+='x';self.assertFalse(self.parse([self.events[0],text,self.events[-1]])['valid'])
        rows=[self.events[0],*([self.events[1]]*99998),self.events[-1]]
        self.assertTrue(self.parse(rows)['valid'])
        self.assertFalse(self.parse([*rows,self.events[-1]])['valid'])

    def test_duplicate_nested_key_and_partial_utf8_fail(self):
        data=json.dumps(self.events[0]).replace('"messageID": "msg_one"','"messageID":"msg_one","messageID":"msg_other"').encode()+b'\n'
        self.assertFalse(self.parse(data=data)['valid'])
        self.assertFalse(self.parse(data=b'{"text":"\xe2\x82"}\n')['valid'])

    def test_safe_capture_rejects_hardlink_and_same_size_hash_drift(self):
        data=b''.join((json.dumps(row)+'\n').encode() for row in self.events);self.path.write_bytes(data)
        alias=self.root/'alias';os.link(self.path,alias)
        self.assertFalse(self.parse(data=data)['valid']);alias.unlink()
        self.assertFalse(self.parse(stdout_sha256='0'*64)['valid'])

    def test_capture_reader_overflow_stops_at_declared_observed_bytes(self):
        original=os.fdopen;reads=[]
        class GrowingReader:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def fileno(self):return self.stream.fileno()
            def readline(self,limit):
                line=self.stream.readline(limit)
                if not line:line=(json.dumps(event('text',part_id='prt_fakegrowth'))+'\n').encode()
                reads.append(len(line));return line
        with patch.object(os,'fdopen',side_effect=lambda *a,**k:GrowingReader(original(*a,**k))):
            result=self.parse()
        self.assertFalse(result['valid']);self.assertEqual(result['reasons'],['stdout_limit']);self.assertEqual(len(reads),4)

    def test_total_stdout_exact_boundary_and_one_byte_overflow(self):
        encode=lambda row:(json.dumps(row,ensure_ascii=False)+'\n').encode()
        start,end=encode(self.events[0]),encode(self.events[-1]);remaining=67108864-len(start)-len(end);parts=[start];index=0
        while remaining:
            row=event('text',part_id='prt_boundary_'+str(index));row['part']['text']=''
            overhead=len(encode(row));size=min(1048576,remaining)
            self.assertGreaterEqual(size,overhead)
            row['part']['text']='x'*(size-overhead);parts.append(encode(row));remaining-=size;index+=1
        parts.append(end);data=b''.join(parts);self.assertEqual(len(data),67108864)
        self.assertTrue(self.parse(data=data)['valid'])
        self.assertFalse(self.parse(data=data+b'\n')['valid'])

    def test_known_credential_or_native_database_is_never_opened_as_capture(self):
        from task_tower import opencode_files
        for name in ('auth.json','kv.json','opencode.db','opencode.db-wal'):
            self.path=self.root/name
            with self.subTest(name=name),patch.object(opencode_files,'_open_readonly',side_effect=OSError('forbidden capture opened')) as opened:
                result=self.parse()
                self.assertFalse(result['valid']);opened.assert_not_called()

    def test_retained_metadata_limit_rejects_independent_review_reproducer(self):
        rows=[self.events[0],*[event('text',part_id='prt_unique_'+str(i)) for i in range(1200)],self.events[-1]]
        result=self.parse(rows)
        self.assertFalse(result['valid']);self.assertEqual(result['reasons'],['metadata_limit'])

    def observe_budget(self,rows):
        original=adapter._EventMetadata;created=[]
        def factory():
            value=original();created.append(value);return value
        with patch.object(adapter,'_EventMetadata',side_effect=factory):result=self.parse(rows)
        budget=created[-1]
        # Independently serialize ALL retained maps/counter reservations.
        normalized={**budget.fixed,**{name:[[key,value] for key,value in mapping.items()] for name,mapping in budget.maps.items()}}
        self.assertEqual(budget.used,len(adapter.canonical(normalized)))
        self.assertLessEqual(budget.used,65536)
        return result,budget

    def test_all_retained_metadata_exact_boundary_and_one_byte_overflow(self):
        tool=event('tool_use');tool['part']['id']='x'
        rows=[self.events[0],tool,self.events[-1]]
        initial,budget=self.observe_budget(rows);self.assertTrue(initial['valid'])
        tool['part']['id']='x'*(1+65536-budget.used)
        exact,full=self.observe_budget(rows)
        self.assertTrue(exact['valid'],exact);self.assertEqual(full.used,65536)
        tool['part']['id']+='x'
        overflow,_=self.observe_budget(rows)
        self.assertFalse(overflow['valid']);self.assertEqual(overflow['reasons'],['metadata_limit'])

    def test_metadata_charges_unique_steps_and_tool_calls_and_reuses_duplicates(self):
        for family in ('steps','tools'):
            if family=='steps':
                rows=[]
                for i in range(400):rows.extend([event('step_start','msg_'+str(i),'prt_start_'+str(i)),event('step_finish','msg_'+str(i),'prt_end_'+str(i))])
            else:
                rows=[self.events[0]]
                for i in range(400):
                    tool=event('tool_use',part_id='prt_tool_'+str(i));tool['part']['id']='call_'+str(i);rows.append(tool)
                rows.append(self.events[-1])
            with self.subTest(family=family):
                result,_=self.observe_budget(rows);self.assertFalse(result['valid']);self.assertEqual(result['reasons'],['metadata_limit'])
        plain,before=self.observe_budget(self.events)
        repeated,after=self.observe_budget([self.events[0],*([self.events[1]]*1000),self.events[-1]])
        self.assertTrue(plain['valid']);self.assertTrue(repeated['valid']);self.assertEqual(before.used,after.used)
        self.assertEqual(repeated['event_count'],1002)

    def test_metadata_update_delta_and_rejected_update_preserve_bound(self):
        budget=adapter._EventMetadata();budget.put('steps','msg_one','started');before=budget.used
        budget.put('steps','msg_one','finished');self.assertEqual(budget.used,before+1)
        overhead=len(adapter.canonical([('msg_one',''),'b'*64]));gap=65536-budget.used-overhead
        budget.put('tool_calls',('msg_one','x'*gap),'b'*64);self.assertEqual(budget.used,65536)
        with self.assertRaisesRegex(ValueError,'metadata_limit'):budget.put('steps','msg_one','finishedX')
        self.assertEqual(budget.maps['steps']['msg_one'],'finished');self.assertEqual(budget.used,65536)
        budget.put('steps','msg_one','finished');self.assertEqual(budget.used,65536)


class InvocationInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.directory=self.root/'attempt';self.directory.mkdir()
        self.snap=self.directory/'instructions';self.snap.mkdir();self.original=self.root/'original';self.original.mkdir()
        manifest={}
        for i in range(60):
            name='skill%02d.md'%i;data=('unchanged skill %d \u044f\n'%i).encode()
            (self.snap/name).write_bytes(data);(self.original/name).write_bytes(data);manifest[name]=hashlib.sha256(data).hexdigest()
        self.profile=dict(kind='opencode',argv=[str(Path(sys.executable).resolve())],superpowers=dict(root=str(self.original),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)))
        self.attempt=dict(directory=str(self.directory),worktree=str(self.directory/'worktree'),run_id=str(uuid.uuid4()),attempt_id=str(uuid.uuid4()),source_sha='b'*40,repository='Owner/Repo',issue=21,task_id='fixture',
            instruction_manifest=manifest,declared_superpowers_revision='a'*40,superpowers_manifest_sha256=profile_fingerprint(manifest),instructions_path=str(self.snap/'skill00.md'),
            request_path=str(self.directory/'request.json'),schema_path=str(self.directory/'schema.json'),result_path=str(self.directory/'result.json'))
        request={key:self.attempt[key] for key in ('run_id','attempt_id','source_sha','repository','issue','task_id','worktree','instructions_path')}
        request.update(version=1,task_data={'body':'untrusted --model attacker'},instruction_manifest=manifest,constraints=[])
        Path(self.attempt['request_path']).write_text(json.dumps(request),encoding='utf8')
        Path(self.attempt['schema_path']).write_text(json.dumps(result_schema(self.attempt)),encoding='utf8')

    def test_fixed_v2_standalone_invocation(self):
        self.assertEqual(adapter.build_opencode_invocation(self.attempt,self.profile),[self.profile['argv'][0],'run','--standalone','--format','json'])
        for argv in ([self.profile['argv'][0],'--model','other'],['x'*17000]):
            with self.subTest(argv_length=len(argv[0])),self.assertRaises(ValueError):adapter.build_opencode_invocation(self.attempt,{**self.profile,'argv':argv})

    def test_quoted_command_size_boundaries_without_native_launch(self):
        actual_safe=adapter.safe_path;info=Path(self.profile['argv'][0]).stat()
        class PathFixture:
            def __init__(self,value):self.value=value
            def __str__(self):return self.value
            def lstat(self):return info
        for platform_limit in ('utf16','utf8'):
            argv=['','run','--standalone','--format','json']
            if platform_limit=='utf16':
                overhead=len(subprocess.list2cmdline(['x',*argv[1:]]).encode('utf-16-le'))//2-1
                candidate='x'*(15999-overhead)
            else:
                remaining=16383-sum(len(value.encode())+1 for value in argv)
                candidate='\u00e9'*(remaining//2)+'x'*(remaining%2)
            for suffix,valid in (('',True),('x',False)):
                value=candidate+suffix;profile={**self.profile,'argv':[value]}
                with self.subTest(platform_limit=platform_limit,valid=valid),patch.object(adapter,'safe_path',side_effect=lambda path:PathFixture(path) if path==value else actual_safe(path)):
                    if valid:self.assertEqual(adapter.build_opencode_invocation(self.attempt,profile)[0],value)
                    else:
                        with self.assertRaises(ValueError):adapter.build_opencode_invocation(self.attempt,profile)

    def test_full60_pins_in_input(self):
        spec=adapter.write_opencode_input(self.attempt,self.profile);data=Path(spec['path']).read_bytes()
        self.assertEqual(set(spec),{'path','expected_sha256','expected_bytes','expected_identity'})
        self.assertEqual(spec['expected_sha256'],hashlib.sha256(data).hexdigest());self.assertEqual(spec['expected_bytes'],len(data))
        for name in sorted(self.attempt['instruction_manifest']):self.assertIn((self.snap/name).read_bytes(),data)
        self.assertIn(b'untrusted --model attacker',data);self.assertIn(json.dumps(self.attempt['result_path']).encode(),data)
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)

    def test_snapshot_drift_and_missing_skill_fail_without_input(self):
        (self.snap/'skill59.md').write_bytes(b'drift')
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
        self.assertFalse((self.directory/'native-input.txt').exists())
        (self.snap/'skill59.md').unlink()
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)

    def test_changed_pins_request_schema_and_oversize_fail_before_input(self):
        original=copy.deepcopy(self.attempt)
        for key,value in [('superpowers_manifest_sha256','0'*64),('declared_superpowers_revision','0'*40)]:
            self.attempt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
            self.attempt=copy.deepcopy(original)
        request_path=Path(self.attempt['request_path']);request=json.loads(request_path.read_text());request['run_id']=str(uuid.uuid4());request_path.write_text(json.dumps(request))
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
        request['run_id']=self.attempt['run_id'];request['task_data']['body']='x'*4194304;request_path.write_text(json.dumps(request))
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
        self.assertFalse((self.directory/'native-input.txt').exists())

    def test_input_stream_conversion_failure_closes_raw_descriptor(self):
        descriptors=[]
        def broken(fd,*args,**kwargs):descriptors.append(fd);raise OSError('producer stream failure')
        with patch.object(os,'fdopen',side_effect=broken):
            with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
        self.assertTrue(descriptors)
        for fd in descriptors:
            try:
                with self.assertRaises(OSError):os.fstat(fd)
            finally:
                try:os.close(fd)
                except OSError:pass

    def test_total_input_exact_boundary_and_one_byte_overflow(self):
        first=adapter.write_opencode_input(self.attempt,self.profile);baseline=first['expected_bytes'];Path(first['path']).unlink()
        request_path=Path(self.attempt['request_path']);request=json.loads(request_path.read_text());body=request['task_data']['body']
        request['task_data']['body']=body+'x'*(4194304-baseline);request_path.write_text(json.dumps(request),encoding='utf8')
        exact=adapter.write_opencode_input(self.attempt,self.profile);self.assertEqual(exact['expected_bytes'],4194304);Path(exact['path']).unlink()
        request['task_data']['body']+='x';request_path.write_text(json.dumps(request),encoding='utf8')
        with self.assertRaises(ValueError):adapter.write_opencode_input(self.attempt,self.profile)
        self.assertFalse(Path(exact['path']).exists())


if __name__=='__main__':unittest.main()
