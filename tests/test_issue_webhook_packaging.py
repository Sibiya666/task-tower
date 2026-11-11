import importlib.util
import tempfile
import unittest
from pathlib import Path
from integrations.github_webhook.package import build,FILES,ROUTES
class PackagingTests(unittest.TestCase):
    def test_deploy_package_contains_only_fixed_receiver_files_and_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"receiver";receipt=build(out)
            files={str(p.relative_to(out)).replace("\\","/") for p in out.rglob("*") if p.is_file()}
            self.assertEqual(files,set(FILES)|{"api/"+p+".py" for p in ROUTES}|{"package-receipt.json"})
            self.assertFalse(any(p.startswith("task_tower/") or ".env" in p or ".git" in p for p in files))
            self.assertEqual(receipt["source_state"],"development")
            spec=importlib.util.spec_from_file_location("staged_webhook",out/"api/github/webhook.py");module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.assertEqual(module.handler.route,"/api/github/webhook")
    def test_packager_never_overwrites_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"receiver";out.mkdir();marker=out/"private.txt";marker.write_text("keep",encoding="utf-8")
            with self.assertRaises(FileExistsError):build(out)
            self.assertEqual(marker.read_text(encoding="utf-8"),"keep")
