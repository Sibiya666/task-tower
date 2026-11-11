"""Fixed HTTP endpoints; configuration injected by operator, no URL proxy.

Deployment packaging/activation is separate. Handler requires Python 3.12+.
"""
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
import json
import sys

from integrations.github_webhook.receiver import MAX_BODY, InvalidDelivery, strict_json, validate_delivery
from integrations.github_webhook.inbox import Inbox, Conflict, Unauthorized, postgres_transactions


class Application:
	def __init__(self, inbox, secret, binding):
		self.inbox, self.secret, self.binding = inbox, secret, binding

	def handle(self, method, path, headers, raw):
		try:
			if method == 'GET' and path == '/api/health':
				self.inbox.health()
				return 200, {'status': 'ok', 'version': 1}
			if method != 'POST' or path not in ('/api/github/webhook', '/api/inbox/take', '/api/inbox/ack', '/api/inbox/replay'):
				return 404, {'error': 'not found'}
			if len(raw) > MAX_BODY:
				return 413, {'error': 'body too large'}
			if path == '/api/github/webhook':
				delivery = validate_delivery(raw, headers, self.secret, self.binding)
				return 202, asdict(self.inbox.record(delivery))
			data = strict_json(raw)
			auth = {k.lower(): v for k, v in headers.items()}.get('authorization', '')
			if not auth.startswith('Bearer '):
				raise Unauthorized()
			consumer = (data['consumer'], auth[7:])
			if path == '/api/inbox/take':
				return 200, {'deliveries': [d.public() for d in self.inbox.take(consumer, self.inbox.clock(), data['limit'])]}
			if path == '/api/inbox/ack':
				return 200, asdict(self.inbox.ack(consumer, data['delivery_id'], data['receipt_hash']))
			return 200, asdict(self.inbox.readback(consumer, data['delivery_id']))
		except Unauthorized:
			return 401, {'error': 'unauthorized'}
		except Conflict:
			return 409, {'error': 'delivery conflict'}
		except (InvalidDelivery, ValueError, KeyError, TypeError, UnicodeError, RecursionError):
			return 400, {'error': 'invalid request'}
		except Exception:
			return 503, {'error': 'durable transport unavailable'}


def configured_application():
	if sys.version_info < (3, 12):
		raise RuntimeError('backend requires Python 3.12+')
	import os
	binding = strict_json(os.environ['WEBHOOK_BINDING'].encode())
	consumers = strict_json(os.environ['WEBHOOK_CONSUMERS'].encode())
	inbox = Inbox(postgres_transactions(os.environ['WEBHOOK_DATABASE_URL']), binding, consumers)
	secret = os.environ['WEBHOOK_SECRET'].encode('utf-8')
	if not secret:
		raise ValueError('empty webhook secret')
	return Application(inbox, secret, binding)


class handler(BaseHTTPRequestHandler):
	def log_message(self, *args):
		pass

	def do_GET(self):
		self._handle()

	def do_POST(self):
		self._handle()

	def _handle(self):
		try:
			lengths = self.headers.get_all('Content-Length', [])
			if self.headers.get('Transfer-Encoding') or len(lengths) > 1:
				raise ValueError()
			length = int(lengths[0]) if lengths else 0
			if not 0 <= length <= MAX_BODY:
				code, body = 413, {'error': 'body too large'}
			else:
				self.connection.settimeout(5)
				raw = self.rfile.read(length)
				if len(raw) != length:
					raise ValueError()
				headers = dict(self.headers)
				if len({k.lower() for k in self.headers}) != len(list(self.headers)):
					raise ValueError()
				code, body = configured_application().handle(self.command, self.path, headers, raw)
		except (ValueError, TimeoutError):
			code, body = 400, {'error': 'invalid framing'}
		except Exception:
			code, body = 503, {'error': 'transport unavailable'}
		encoded = json.dumps(body, ensure_ascii=True).encode('utf-8')
		self.send_response(code)
		self.send_header('Content-Type', 'application/json')
		self.send_header('Content-Length', str(len(encoded)))
		self.send_header('Cache-Control', 'no-store')
		self.end_headers()
		self.wfile.write(encoded)
