"""Real relational query controls; the external Dolt process is the only double."""
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


class DoltEventTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);exe=self.root/'dolt';exe.write_bytes(b'fixture-dolt')
        self.profile=dict(executable=str(exe),sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),version='1.85.0',
            host='127.0.0.1',port=14444,database='proof',user='root',password_file=None,
            project_id='d16b34dd-b706-4d07-aa0f-1fc5d7c7b294')
        import json
        (self.root/'.beads').mkdir()
        raw=json.dumps(dict(database='beads.db',project_id=self.profile['project_id'],dolt_mode='server',dolt_server_host='127.0.0.1',
            dolt_server_port=14444,dolt_database='proof',dolt_server_user='root')).encode('utf-8')
        (self.root/'.beads/metadata.json').write_bytes(raw);self.profile['metadata_sha256']=hashlib.sha256(raw).hexdigest()
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close);self.db.row_factory=sqlite3.Row
        self.db.executescript("CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE wisps(id TEXT);"+
            ''.join('CREATE TABLE '+name+'(id TEXT,issue_id TEXT,event_type TEXT,actor TEXT,old_value TEXT,new_value TEXT,comment TEXT,created_at TEXT);' for name in ('events','wisp_events')))
        self.db.execute('INSERT INTO metadata VALUES (?,?)',('_project_id',self.profile['project_id']))
        self.row=('ecfcf609-90b2-42ab-837c-cdbf71bdf132','pilot-a','closed','owner','','exact reason','','2026-11-08T00:00:00Z')

    def runner(self,argv,cwd,timeout,env):
        self.assertEqual(argv[:11],[self.profile['executable'],'--host','127.0.0.1','--port','14444','--use-db','proof','--user','root','--no-tls','sql'])
        self.assertNotEqual(cwd,self.root)
        self.assertEqual(Path(env['DOLT_ROOT_PATH']),cwd/'home')
        self.assertEqual(env['DOLT_DISABLE_EVENT_FLUSH'],'1')
        self.assertEqual((cwd/'home/.dolt/config_global.json').read_text(encoding='utf-8'),'{"metrics.disabled":"true","versioncheck.disabled":"true"}\n')
        self.assertFalse(any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN','DOLT_PROFILE') for k in env))
        self.assertNotIn('--password',argv)
        query=argv[-1];self.assertTrue(query.startswith('SELECT '));self.assertNotIn(';',query)
        # Dolt1.85 jsonDataForSqlSchema skips every SQL NULL column.
        return {'rows':[{k:v for k,v in dict(r).items() if v is not None} for r in self.db.execute(query)]}

    def test_authentic_null_omissions_preserve_optional_values_but_never_invent_identity(self):
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',
            (self.row[0],self.row[1],'created','owner',None,None,None,self.row[-1]))
        try:events=read_events(self.root,'pilot-a',self.profile,self.runner,10)
        except ServiceError as error:self.fail('authentic Dolt NULL omission rejected: '+error.code)
        self.assertEqual(events[0]['id'],'ecfcf609-90b2-42ab-837c-cdbf71bdf132')
        self.assertEqual([events[0][k] for k in ('old_value','new_value','comment')],[None,None,None])
        for missing in ('id','issue_id','event_type','actor','created_at','project_id'):
            def invalid(argv,cwd,timeout,env):
                result=self.runner(argv,cwd,timeout,env)
                for row in result['rows']:
                    if row['row_kind']=='event':row.pop(missing)
                return result
            with self.subTest(missing=missing),self.assertRaises(ServiceError):
                read_events(self.root,'pilot-a',self.profile,invalid,10)

    def test_native_project_event_identity_and_actual_wisp_membership(self):
        from task_tower.service.dolt_events import read_events
        self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',self.row)
        with patch.dict(os.environ,{'DOLT_PROFILE':'foreign','gH_tOkEn':'secret'}):
            events=read_events(self.root,'pilot-a',self.profile,self.runner,10)
        self.assertEqual(events,[dict(zip(('id','issue_id','event_type','actor','old_value','new_value','comment','created_at'),self.row))])
        self.db.execute('INSERT INTO wisps VALUES (?)',('pilot-a',))
        self.assertEqual(read_events(self.root,'pilot-a',self.profile,self.runner,10),[])
        self.db.execute('INSERT INTO wisp_events VALUES (?,?,?,?,?,?,?,?)',self.row)
        self.assertEqual(read_events(self.root,'pilot-a',self.profile,self.runner,10)[0]['new_value'],'exact reason')

    def test_wrong_project_overflow_and_duplicate_native_ids_fail_closed(self):
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        self.db.execute('UPDATE metadata SET value=?',('another-project',))
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,self.runner,10)
        self.db.execute('UPDATE metadata SET value=?',(self.profile['project_id'],))
        self.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',[self.row,self.row])
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,self.runner,10)
        self.db.execute('DELETE FROM events')
        import uuid
        self.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',[(str(uuid.uuid4()),*self.row[1:]) for _ in range(101)])
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,self.runner,10)

    def test_injection_or_changed_binary_never_spawns_reader(self):
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        def forbidden(*args):self.fail('untrusted reader spawned')
        with self.assertRaises(ServiceError):read_events(self.root,"pilot-a' OR 1=1",self.profile,forbidden,10)
        Path(self.profile['executable']).write_bytes(b'changed')
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,forbidden,10)

    def test_local_env_redirect_missing_or_changed_metadata_never_spawns_reader(self):
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        def forbidden(*args):self.fail('untrusted source read')
        for name in ('.env','redirect'):
            path=self.root/'.beads'/name;path.write_text('foreign',encoding='utf-8')
            with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,forbidden,10)
            path.unlink()
        path=self.root/'.beads/metadata.json';path.write_text('{}',encoding='utf-8')
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,forbidden,10)
        path.unlink()
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,forbidden,10)

    def test_legacy_producer_omits_false_tls_but_true_and_bad_types_fail_closed(self):
        import json
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        path=self.root/'.beads/metadata.json'
        metadata=json.loads(path.read_text(encoding='utf-8'))
        def save():
            raw=json.dumps(metadata).encode('utf-8');path.write_bytes(raw)
            self.profile['metadata_sha256']=hashlib.sha256(raw).hexdigest()
        save()
        try:self.assertEqual(read_events(self.root,'pilot-a',self.profile,self.runner,10),[])
        except ServiceError as error:self.fail('native1.0.2 omitempty false rejected: '+error.code)
        metadata['dolt_server_tls']=False;save()
        self.assertEqual(read_events(self.root,'pilot-a',self.profile,self.runner,10),[])
        for invalid in (True,0,'false',None):
            metadata['dolt_server_tls']=invalid;save()
            with self.subTest(tls=invalid),self.assertRaises(ServiceError):
                read_events(self.root,'pilot-a',self.profile,self.runner,10)

    def test_unknown_metadata_field_is_not_registered_by_hash_alone(self):
        import json
        from task_tower.service.dolt_events import read_events
        from task_tower.service.beads import ServiceError
        path=self.root/'.beads/metadata.json';metadata=json.loads(path.read_text(encoding='utf-8'))
        metadata['unrecognized_routing_option']='foreign'
        raw=json.dumps(metadata).encode('utf-8');path.write_bytes(raw);self.profile['metadata_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ServiceError):read_events(self.root,'pilot-a',self.profile,self.runner,10)
