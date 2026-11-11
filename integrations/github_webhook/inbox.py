"""Transport only. Inject context-managed DB-API transactions; exit commits."""
import contextlib
from dataclasses import dataclass
import hashlib
import hmac
import re
import time

from .receiver import Delivery, strict_json

SCOPE = 'app_id=%s AND installation_id=%s AND repository_id=%s'
RETENTION = 30 * 86400


class Conflict(ValueError):
	pass


class Unauthorized(ValueError):
	pass


@dataclass(frozen=True)
class Receipt:
	delivery_id: str
	payload_sha256: str
	state: str
	receipt_hash: str | None


def postgres_transactions(dsn):
	@contextlib.contextmanager
	def transaction():
		import psycopg
		with psycopg.connect(dsn, connect_timeout=5, options='-c statement_timeout=5000 -c lock_timeout=5000') as db:
			yield db
	return transaction


class Inbox:
	def __init__(self, transaction, binding, consumers, clock=time.time):
		self.transaction, self.clock = transaction, clock
		self.scope = tuple(binding[k] for k in ('app_id', 'installation_id', 'repository_id'))
		if any(type(v) is not int or v <= 0 for v in self.scope):
			raise ValueError('invalid binding')
		self.consumers = {}
		for name, config in consumers.items():
			scope = tuple(config[k] for k in ('app_id', 'installation_id', 'repository_id'))
			if scope != self.scope or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name):
				raise ValueError('consumer binding mismatch')
			digest = config['credential_sha256']
			if not re.fullmatch(r'[0-9a-f]{64}', digest):
				raise ValueError('invalid credential hash')
			self.consumers[name] = digest
		if len(self.consumers) != 1:
			raise ValueError('repository requires exactly one configured consumer')

	def _consumer(self, consumer):
		try:
			name, token = consumer
			digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
			if not hmac.compare_digest(self.consumers.get(name, '0'*64), digest) or name not in self.consumers:
				raise Unauthorized('invalid credential')
			return name
		except (TypeError, ValueError, AttributeError) as exc:
			raise Unauthorized('invalid credential') from exc

	def _receipt(self, db, delivery_id):
		row = db.execute('SELECT delivery_id,payload_sha256,state,receipt_hash FROM webhook_inbox WHERE '+
						 SCOPE+' AND delivery_id=%s', self.scope+(delivery_id,)).fetchone()
		if row is None:
			raise Conflict('delivery not found')
		return Receipt(*row)

	def record(self, delivery) -> Receipt:
		if (delivery.app_id, delivery.installation_id, delivery.repository_id) != self.scope:
			raise Conflict('source mismatch')
		with self.transaction() as db:
			db.execute('INSERT INTO webhook_inbox '
					   '(app_id,installation_id,repository_id,delivery_id,payload_sha256,event,action,body,created_at) '
					   'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
					   self.scope+(delivery.delivery_id, delivery.payload_sha256, delivery.event,
								   delivery.action, delivery.raw, self.clock()))
			receipt = self._receipt(db, delivery.delivery_id)
			if receipt.payload_sha256 != delivery.payload_sha256:
				raise Conflict('delivery hash conflict')
		return receipt

	def take(self, consumer, now, limit) -> list[Delivery]:
		name = self._consumer(consumer)
		if type(limit) is not int or not 1 <= limit <= 100:
			raise ValueError('limit must be 1..100')
		self.prune(now)
		with self.transaction() as db:
			db.execute("UPDATE webhook_inbox SET state='failed' WHERE "+SCOPE+
					   " AND state='pending' AND attempts=5 AND next_at<=%s", self.scope+(now,))
			rows = db.execute('SELECT delivery_id,payload_sha256,event,action,body,attempts FROM webhook_inbox WHERE '+
							  SCOPE+" AND state='pending' AND body IS NOT NULL AND attempts<5 AND next_at<=%s "+
							  'ORDER BY created_at,delivery_id LIMIT %s FOR UPDATE SKIP LOCKED',
							  self.scope+(now, limit)).fetchall()
			deliveries = []
			for delivery_id, digest, event, action, raw, attempts in rows:
				db.execute('UPDATE webhook_inbox SET attempts=attempts+1,next_at=%s,lease_consumer=%s WHERE '+
						   SCOPE+' AND delivery_id=%s', (now+60+2**attempts, name)+self.scope+(delivery_id,))
				raw = bytes(raw)
				deliveries.append(Delivery(1, *self.scope, delivery_id, digest, event, action, strict_json(raw), raw))
		return deliveries

	def ack(self, consumer, delivery_id, receipt_hash) -> Receipt:
		name = self._consumer(consumer)
		if not isinstance(receipt_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', receipt_hash):
			raise Conflict('invalid effect receipt hash')
		with self.transaction() as db:
			db.execute("UPDATE webhook_inbox SET state='acked',receipt_hash=%s WHERE "+SCOPE+
					   ' AND delivery_id=%s AND lease_consumer=%s AND receipt_hash IS NULL',
					   (receipt_hash,)+self.scope+(delivery_id, name))
			receipt = self._receipt(db, delivery_id)
			if receipt.receipt_hash != receipt_hash:
				raise Conflict('ACK missing lease or effect hash mismatch')
		return receipt

	def readback(self, consumer, delivery_id) -> Receipt:
		self._consumer(consumer)
		with self.transaction() as db:
			result = self._receipt(db, delivery_id)
		return result

	def prune(self, now):
		with self.transaction() as db:
			db.execute("UPDATE webhook_inbox SET body=NULL,state=CASE WHEN state='acked' THEN state ELSE 'failed' END WHERE "+
					   SCOPE+' AND created_at<=%s AND body IS NOT NULL', self.scope+(now-RETENTION,))

	def health(self):
		with self.transaction() as db:
			db.execute('SELECT 1').fetchone()


def check_postgres():
	"""Explicit operator SQL smoke; dedicated disposable DB with schema applied."""
	import os
	import uuid
	key = uuid.uuid4().hex
	binding = dict(app_id=1, installation_id=2, repository_id=3)
	hosts = {'check': dict(**binding, credential_sha256=hashlib.sha256(key.encode()).hexdigest())}
	box = Inbox(postgres_transactions(os.environ['WEBHOOK_TEST_DATABASE_URL']), binding, hosts)
	raw = b'{}'
	delivery = Delivery(1, 1, 2, 3, key, hashlib.sha256(raw).hexdigest(), 'issues', '', {}, raw)
	receipt = box.record(delivery)
	assert box.record(delivery) == receipt
	assert [d.delivery_id for d in box.take(('check', key), time.time(), 1)] == [key]
	assert box.ack(('check', key), key, 'a'*64).receipt_hash == 'a'*64
	print('SQL smoke committed; full SQL fault/concurrency deployment gate remains')


if __name__ == '__main__':
	import sys
	if sys.argv[1:] != ['--check-postgres']:
		raise SystemExit('usage: python -m integrations.github_webhook.inbox --check-postgres')
	check_postgres()
