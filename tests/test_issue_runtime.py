import tempfile
import unittest
from pathlib import Path
from task_tower.issue_runtime import runtime_config,scope_parameters
class RuntimeTests(unittest.TestCase):
    def test_declared_existing_file_gets_write_without_granting_repo_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/"docs").mkdir();(root/"docs/example.md").write_text("example",encoding="utf-8")
            config=runtime_config(root,["docs/example.md"])
            self.assertEqual(config['permissions.task-tower-issue.filesystem.":workspace_roots"."."'],"read")
            self.assertEqual(config['permissions.task-tower-issue.filesystem.":workspace_roots"."docs/example.md"'],"write")
            self.assertFalse(config['permissions.task-tower-issue.network.enabled'])
            self.assertNotIn("approval_policy",config)
    def test_sensitive_path_and_missing_file_are_rejected_before_start(self):
        with tempfile.TemporaryDirectory() as temp:
            for path in ["task_tower/service/store.py","../README.md","docs/missing.md"]:
                with self.subTest(path=path),self.assertRaises(ValueError):runtime_config(Path(temp),[path])
    def test_manual_commands_keep_existing_runtime_contract(self):
        self.assertEqual(scope_parameters({},Path.cwd()),{})

    def test_closed_port_and_timeout_never_count_as_proven_network_denial(self):
        import errno
        from task_tower.issue_runtime import network_denied
        self.assertFalse(network_denied(ConnectionRefusedError(errno.ECONNREFUSED,"closed port")))
        self.assertFalse(network_denied(TimeoutError("unknown reachability")))
        self.assertTrue(network_denied(PermissionError(errno.EACCES,"denied")))

    def test_issue_scope_reaches_real_appserver_request_through_connector_journal(self):
        import time
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.app_server import AppServer
        class Wire:
            def request(_,method,params):
                self.assertEqual(method,"thread/start")
                profile=params["config"]["permissions"]["task-tower-issue"]
                self.assertEqual(profile["filesystem"][":workspace_roots"]["docs/example.md"],"write")
                self.assertFalse(profile["network"]["enabled"])
                return dict(thread=dict(id="thread"))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/"docs").mkdir();(root/"docs/example.md").write_text("example",encoding="utf-8")
            store=ConnectorStore(root/"journal","connector")
            try:
                command=dict(version=1,kind="execute",command_id="scope-command",attempt_id="attempt",project_id="p",base_sha="a"*40,input=dict(text="approved request"),source=dict(head_sha="a"*40,base_sha="a"*40,diff=""),issue_scope=dict(paths=["docs/example.md"],deadline=time.time()+60))
                store.receive(command)
                app=AppServer(store,transport=Wire())
                self.assertEqual(app.create_thread(root,"scope-command"),"thread")
            finally:store.close()

    def test_issue_base_uses_fetched_head_with_a_narrow_clone_refspec(self):
        from types import SimpleNamespace
        from task_tower.issue_runtime import IssueScopeInspector
        class Git:
            def _remote(_,root,repository):pass
            def _trusted_git(_,root,*args,**kwargs):
                if args[0]=="fetch":return ""
                if args[:2]==("rev-parse","FETCH_HEAD"):return "b"*40
                if args[:2]==("rev-parse","refs/remotes/origin/main"):return "a"*40
                if args[0]=="ls-tree":return "100644 blob "+"c"*40+"\tdocs/example.md"
                raise AssertionError(args)
        probe=SimpleNamespace(verify=lambda:dict(checks=dict(verified=True)))
        result=IssueScopeInspector(Git(),Path.cwd(),"Sibiya666/task-tower",probe)(["docs/example.md"])
        self.assertEqual(result["base_sha"],"b"*40)
