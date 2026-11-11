import hashlib
import hmac
import unittest
from integrations.github_webhook.api.index import Application
class HandshakeTests(unittest.TestCase):
    def test_signed_ping_can_complete_setup_without_native_or_inbox_effects(self):
        raw=b'{"zen":"test"}';secret=b"synthetic-secret"
        app=Application(None,secret,dict(app_id=7,installation_id=8,repository_id=9))
        headers={"X-GitHub-Event":"ping","X-Hub-Signature-256":"sha256="+hmac.new(secret,raw,hashlib.sha256).hexdigest()}
        self.assertEqual(app.handle("POST","/api/github/webhook",headers,raw),(200,{"status":"pong","event":"ping"}))
        headers["X-Hub-Signature-256"]="sha256="+"0"*64
        self.assertEqual(app.handle("POST","/api/github/webhook",headers,raw)[0],400)
