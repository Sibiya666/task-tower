import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

from task_tower import executor_harness as harness


class ClaudeAdapterTests(unittest.TestCase):
    def adapter(self):
        # Assert the missing interface as a test failure during RED, not an import error.
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('task_tower.claude_adapter'),
                             'Claude adapter is not implemented')
        from task_tower import claude_adapter
        return claude_adapter

    def help_bytes(self):
        return b'''Usage: claude [options]
  -p, --print  Print response
  --output-format <format>  choices: "text", "json", "stream-json"
  --verbose  Verbose output
  --json-schema <schema>  JSON schema
  --safe-mode  Preserve auth and model
  --permission-mode <mode>  choices: "manual", "plan"
  --permission-prompts <target>  choices: "host", "none"
  --tools <tools...>  Built-in tools
  --allowedTools, --allowed-tools <tools...>  Approved tools
  --strict-mcp-config  Strict MCP
  --mcp-config <configs...>  MCP file
  --no-chrome  Disable browser
  --session-id <uuid>  Session
  --max-budget-usd <amount>  Approximate budget
'''

    def test_probe_requires_supported_version_and_each_actual_option(self):
        api=self.adapter(); version=b'2.1.302 (Claude Code)\n'; help_data=self.help_bytes()
        value=api.validate_probe(version,help_data,'2.1.302')
        self.assertTrue(value['version_supported']); self.assertTrue(value['required_options_validated'])
        self.assertEqual(value['version'],'2.1.302')
        self.assertNotIn('raw',value)
        for line in help_data.splitlines()[1:]:
            with self.subTest(line=line):
                with self.assertRaises(ValueError): api.validate_probe(version,help_data.replace(line+b'\n',b''),'2.1.302')
        for bad in [b'2.1.303 (Claude Code)',b'2.1.302 fake',b'\xff',b'x'*65537]:
            with self.assertRaises(ValueError): api.validate_probe(bad,help_data,'2.1.302')
        for bad in [help_data.replace(b'"manual"',b'"auto"'),help_data.replace(b'"none"',b'"host"'),
                    help_data.replace(b'"stream-json"',b'"other"'),b'\xff',b'x'*1048577]:
            with self.assertRaises(ValueError): api.validate_probe(version,bad,'2.1.302')
        with self.assertRaises(ValueError): api.validate_probe(version,help_data,'2.1.303')

    def test_probe_does_not_accept_option_mentioned_only_in_description(self):
        api=self.adapter(); data=self.help_bytes().replace(b'  --safe-mode  Preserve auth and model\n',b'')
        data+=b'  --other  Consider --safe-mode someday\n'
        with self.assertRaises(ValueError): api.validate_probe(b'2.1.302 (Claude Code)',data,'2.1.302')

    def test_mcp_preparation_is_exclusive_and_drift_rejected(self):
        api=self.adapter()
        with tempfile.TemporaryDirectory() as raw:
            value=api.prepare_mcp_config(Path(raw).resolve())
            path=Path(value['mcp_path']); data=path.read_bytes()
            self.assertEqual(json.loads(data),{'mcpServers':{}})
            self.assertEqual(value['mcp_sha256'],hashlib.sha256(data).hexdigest())
            with self.assertRaises(ValueError): api.prepare_mcp_config(Path(raw).resolve())
            attempt=self.attempt()|value
            path.write_text('{"mcpServers":{"unexpected":{}}}')
            with self.assertRaises(ValueError): api.build_claude_invocation(attempt,self.profile())

    def attempt(self):
        return dict(run_id=str(uuid.uuid4()),attempt_id=str(uuid.uuid4()),source_sha='a'*40,
                    request_content={'task_data':{'body':'Fix one file; --model injected is data'}},
                    instruction_content='Pinned instruction text')

    def profile(self,role='implementer'):
        return dict(kind='claude',argv=['claude.exe'],trusted=False,approve_for_me=False,
                    claude=dict(version='2.1.302',role=role,max_budget_usd='0.25',
                                stream_max_bytes=65536,line_max_bytes=4096))

    def test_fixed_invocation_has_inline_context_and_explicit_role_tools(self):
        api=self.adapter()
        with tempfile.TemporaryDirectory() as raw:
            attempt=self.attempt()|api.prepare_mcp_config(Path(raw).resolve())
            for role,tools in [('implementer','Read,Edit,Write,Glob,Grep'),('reviewer','Read,Glob,Grep')]:
                argv=api.build_claude_invocation(attempt,self.profile(role))
                self.assertEqual(argv,harness.build_invocation(attempt,self.profile(role)))
                for flag,value in [('--output-format','stream-json'),('--permission-mode','manual'),
                                   ('--permission-prompts','none'),('--session-id',attempt['attempt_id']),
                                   ('--tools',tools),('--allowedTools',tools),('--max-budget-usd','0.25')]:
                    self.assertEqual(argv[argv.index(flag)+1],value)
                for flag in ['--model','--fallback-model','--effort','--max-turns','--bare','--restricted',
                             '--dangerously-skip-permissions','--resume','--continue','--bg','--add-dir']:
                    self.assertNotIn(flag,argv[:-1])
                self.assertIn('--safe-mode',argv); self.assertIn('--strict-mcp-config',argv)
                self.assertIn('Pinned instruction text',argv[-1])
                self.assertIn('Fix one file',argv[-1])
                schema=json.loads(argv[argv.index('--json-schema')+1])
                self.assertEqual(schema,harness.result_schema(attempt))

    def test_capabilities_do_not_promote_fixtures_to_installed_execution(self):
        api=self.adapter(); profile=self.profile()
        value=api.claude_capabilities(profile)
        for field in ['probed','verified','events','resume','automatic_resume','version_supported',
                      'protocol_validated','installed_execution_verified','independent_review_verified']:
            self.assertFalse(value[field],field)
        self.assertEqual(harness.capabilities(profile),value)
        evidence=dict(probed=True,version_supported=True,protocol_validated=True,
                      installed_execution_verified=True,independent_review_verified=True,evidence_kind='fixture')
        value=api.claude_capabilities(profile,evidence)
        self.assertTrue(value['protocol_validated'])
        self.assertFalse(value['installed_execution_verified']); self.assertFalse(value['verified'])
        self.assertFalse(value['resume']); self.assertFalse(value['automatic_resume'])

    def test_child_environment_disables_updates_without_changing_host_or_model_auth(self):
        api=self.adapter()
        self.assertTrue(hasattr(api,'claude_child_environment'),'Claude update guard is missing')
        host={'GH_TOKEN':'github-secret','gItHuB_tOkEn':'other-secret',
              'DISABLE_UPDATES':'0','disable_updates':'false','Disable_Updates':'',
              'FORCE_AUTOUPDATE_PLUGINS':'1','force_autoupdate_plugins':'true',
              'ANTHROPIC_API_KEY':'existing-auth','ANTHROPIC_MODEL':'existing-model',
              'DISABLE_TELEMETRY':'0','PATH':'existing-path','OTHER':'unchanged'}
        original=dict(host)
        self.assertEqual(api.claude_child_environment(host),{
            'DISABLE_UPDATES':'1','ANTHROPIC_API_KEY':'existing-auth',
            'ANTHROPIC_MODEL':'existing-model','DISABLE_TELEMETRY':'0',
            'PATH':'existing-path','OTHER':'unchanged'})
        self.assertEqual(host,original)
        from task_tower.executor_profiles import child_environment
        self.assertEqual(child_environment(host),{k:v for k,v in original.items()
                                                  if k not in ('GH_TOKEN','gItHuB_tOkEn')})

    def test_hardlinked_mcp_cannot_be_used_for_invocation(self):
        api=self.adapter()
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve(); mcp=api.prepare_mcp_config(root)
            os.link(mcp['mcp_path'],root/'alias.json')
            with self.assertRaises(ValueError):
                api.build_claude_invocation(self.attempt()|mcp,self.profile())

    @unittest.skipUnless(os.name=='nt','Windows junction test')
    def test_actual_windows_junction_cannot_receive_private_mcp(self):
        api=self.adapter()
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve(); target=root/'target'; target.mkdir(); alias=root/'junction'
            result=subprocess.run(['cmd','/c','mklink','/J',str(alias),str(target)],
                                  capture_output=True,timeout=10)
            if result.returncode:
                self.skipTest('junction creation unavailable')
            with self.assertRaises(ValueError): api.prepare_mcp_config(alias)
            self.assertFalse((target/'claude-mcp.json').exists())
