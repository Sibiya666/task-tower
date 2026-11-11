"""Deterministic SQL transaction contracts; PostgreSQL is a separate gate."""
import contextlib
import hashlib
import hmac
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from integrations.github_webhook.receiver import validate_delivery, InvalidDelivery
from integrations.github_webhook.inbox import Inbox, Conflict, Unauthorized
from integrations.github_webhook.api.index import Application

KEY = b'test-secret'
BIND = dict(app_id=1, installation_id=2, repository_id=3)
HOST = ('host', 'test-credential')
HOSTS = {'host': dict(**BIND, credential_sha256=hashlib.sha256(HOST[1].encode()).hexdigest())}
EFFECT = 'a'*64


def event(body=None):
	body = body or dict(installation=dict(id=2), repository=dict(id=3), text='\u041f\u0440\u0438\u0432\u0435\u0442')
	raw = json.dumps(body, ensure_ascii=False).encode()
	return raw, {'X-GitHub-Delivery': 'delivery-1', 'X-GitHub-Event': 'issues',
				 'X-Hub-Signature-256': 'sha256='+hmac.new(KEY, raw, hashlib.sha256).hexdigest()}


class Database:
	"""Execute real SQL with serialized SQLite locking and commit fault injection."""
	def __init__(self):
		self.db = sqlite3.connect(':memory:', check_same_thread=False, isolation_level=None)
		self.db.executescript(Path('integrations/github_webhook/schema.sql').read_text(encoding='utf-8'))
		self.lock = threading.Lock()
		self.fail_commit = False

	@contextlib.contextmanager
	def __call__(self):
		with self.lock:
			self.db.execute('BEGIN')
			try:
				yield self
				if self.fail_commit:
					raise OSError('commit unavailable')
				self.db.execute('COMMIT')
			except BaseException:
				self.db.execute('ROLLBACK')
				raise

	def execute(self, sql, args=()):
		return self.db.execute(sql.replace('%s', '?').replace(' FOR UPDATE SKIP LOCKED', ''), args)


class TransportTests(unittest.TestCase):
	def setUp(self):
		self.db, self.now = Database(), 1000
		self.addCleanup(self.db.db.close)
		self.box = Inbox(self.db, BIND, HOSTS, clock=lambda: self.now)
		self.app = Application(self.box, KEY, BIND)

	def item(self, body=None):
		return validate_delivery(*event(body), KEY, BIND)

	def post(self, path, data, auth=True):
		headers = {'Authorization': 'Bearer '+HOST[1]} if auth else {}
		return self.app.handle('POST', '/api/inbox/'+path, headers, json.dumps(dict(consumer='host', **data)).encode())

	def test_raw_unicode_signature_and_lazy_backend(self):
		result = self.item()
		self.assertEqual(result.body['text'], '\u041f\u0440\u0438\u0432\u0435\u0442')
		self.assertEqual(result.payload_sha256, hashlib.sha256(event()[0]).hexdigest())
		self.assertEqual(result.version, 1)
		self.assertFalse({'owner', 'lifecycle'} & vars(result).keys())
		with patch.dict('sys.modules', {'psycopg': None}):
			self.assertEqual(self.app.handle('GET', '/api/health', {}, b'')[0], 200)

	def test_signature_precedes_json_and_rejects_malformed(self):
		for sig in (None, '', 'sha1='+'0'*64, 'sha256=bad', 'sha256='+'0'*64):
			raw, headers = event()
			headers.pop('X-Hub-Signature-256')
			if sig is not None:
				headers['X-Hub-Signature-256'] = sig
			with patch('integrations.github_webhook.receiver.json.loads') as loads:
				with self.assertRaises(InvalidDelivery):
					validate_delivery(raw, headers, KEY, BIND)
				loads.assert_not_called()

	def test_size_limit_and_binding(self):
		with self.assertRaises(InvalidDelivery):
			validate_delivery(b'x'*1048577, event()[1], KEY, BIND)
		for key in ('installation', 'repository'):
			body = json.loads(event()[0])
			body[key]['id'] = 99
			with self.assertRaises(InvalidDelivery):
				self.item(body)
		body = json.loads(event()[0])
		body['pad'] = ''
		body['pad'] = 'x'*(1048576-len(event(body)[0]))
		self.assertEqual(len(event(body)[0]), 1048576)
		self.assertEqual(self.item(body).repository_id, 3)

	def test_duplicate_hash_conflict_and_replay(self):
		first = self.box.record(self.item())
		self.assertEqual(first, self.box.record(self.item()))
		body = dict(self.item().body, action='edited')
		with self.assertRaises(Conflict):
			self.box.record(self.item(body))
		self.assertEqual(self.box.readback(HOST, 'delivery-1'), first)
		self.assertEqual(len(self.box.take(HOST, self.now, 1)), 1)
		self.assertEqual(self.box.take(HOST, self.now, 1), [])

	def test_racing_consumers_and_scope(self):
		self.box.record(self.item())
		with ThreadPoolExecutor(2) as pool:
			results = pool.map(lambda _: self.box.take(HOST, self.now, 1), range(2))
			self.assertEqual(sum(map(len, results)), 1)
		for host in (('host', 'wrong'), ('other', HOST[1])):
			with self.assertRaises(Unauthorized):
				self.box.take(host, self.now, 1)
		with self.assertRaises(ValueError):
			Inbox(self.db, BIND, dict(HOSTS, other=HOSTS['host']))

	def test_ack_requires_lease_and_preserves_effect_hash(self):
		self.box.record(self.item())
		with self.assertRaises(Conflict):
			self.box.ack(HOST, 'delivery-1', EFFECT)
		self.box.take(HOST, self.now, 1)
		for digest in ('bad',):
			with self.assertRaises(Conflict):
				self.box.ack(HOST, 'delivery-1', digest)
		receipt = self.box.ack(HOST, 'delivery-1', EFFECT)
		self.assertEqual(receipt, self.box.ack(HOST, 'delivery-1', EFFECT))
		with self.assertRaises(Conflict):
			self.box.ack(HOST, 'delivery-1', 'b'*64)
		self.assertEqual(self.box.take(HOST, self.now+9999, 1), [])

	def test_five_attempts_backoff_retained_failure(self):
		self.box.record(self.item())
		for attempt in range(5):
			self.assertEqual(len(self.box.take(HOST, self.now, 1)), 1)
			self.assertEqual(self.box.take(HOST, self.now+1, 1), [])
			self.now += 60+2**attempt
		self.assertEqual(self.box.take(HOST, self.now, 1), [])
		self.assertEqual(self.box.readback(HOST, 'delivery-1').state, 'failed')
		self.assertEqual(self.box.ack(HOST, 'delivery-1', EFFECT).state, 'acked')

	def test_retention_keeps_dedup_and_receipt(self):
		self.box.record(self.item())
		self.box.take(HOST, self.now, 1)
		self.box.ack(HOST, 'delivery-1', EFFECT)
		self.now += 30*86400
		self.box.prune(self.now)
		self.assertEqual(self.db.db.execute('SELECT body FROM webhook_inbox').fetchone(), (None,))
		self.assertEqual(self.box.record(self.item()).receipt_hash, EFFECT)
		self.assertEqual(self.box.readback(HOST, 'delivery-1').state, 'acked')
		self.assertEqual(self.box.take(HOST, self.now, 1), [])

	def test_durable_failure_never_returns_2xx_or_effects(self):
		raw, headers = event()
		with patch('subprocess.Popen', side_effect=AssertionError('native/model effect')), \
			 patch('urllib.request.urlopen', side_effect=AssertionError('GitHub effect')):
			self.db.fail_commit = True
			self.assertEqual(self.app.handle('POST', '/api/github/webhook', headers, raw)[0], 503)
			self.assertEqual(self.db.db.execute('SELECT count(*) FROM webhook_inbox').fetchone()[0], 0)
			self.db.fail_commit = False
			for _ in range(2):
				self.assertEqual(self.app.handle('POST', '/api/github/webhook', headers, raw)[0], 202)
			self.assertEqual(self.app.handle('POST', '/api/proxy', {}, raw)[0], 404)

	def test_http_consumer_auth_readback_health(self):
		self.box.record(self.item())
		self.assertEqual(self.post('take', dict(limit=1), False)[0], 401)
		code, body = self.post('take', dict(limit=1))
		self.assertEqual(code, 200)
		self.assertEqual(body['deliveries'][0]['delivery_id'], 'delivery-1')
		for path, data in (('ack', dict(receipt_hash=EFFECT)), ('replay', {})):
			code, body = self.post(path, dict(delivery_id='delivery-1', **data))
			self.assertEqual((code, body['receipt_hash']), (200, EFFECT))
			self.assertNotIn(HOST[1], json.dumps(body))
		self.assertEqual(self.app.handle('GET', '/api/health', {}, b''), (200, dict(status='ok', version=1)))


if __name__ == '__main__':
	unittest.main()
