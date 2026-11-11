"""Pure raw-byte authentication. No backend imports or downstream effects."""
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import re

MAX_BODY = 1048576


class InvalidDelivery(ValueError):
	pass


@dataclass(frozen=True)
class Delivery:
	version: int
	app_id: int
	installation_id: int
	repository_id: int
	delivery_id: str
	payload_sha256: str
	event: str
	action: str
	body: dict
	raw: bytes = field(repr=False)

	def public(self):
		return {k: v for k, v in vars(self).items() if k != 'raw'}


def strict_json(raw):
	def pairs(items):
		result = {}
		for key, value in items:
			if key in result:
				raise ValueError('duplicate JSON key')
			result[key] = value
		return result
	return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
					  parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def validate_delivery(raw: bytes, headers, secret: bytes, binding) -> Delivery:
	if not isinstance(raw, bytes) or len(raw) > MAX_BODY or not secret:
		raise InvalidDelivery('invalid body or configuration')
	headers = {k.lower(): v for k, v in headers.items()}
	signature = headers.get('x-hub-signature-256', '')
	if not isinstance(signature, str) or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature):
		raise InvalidDelivery('invalid signature')
	expected = 'sha256=' + hmac.new(secret, raw, hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, signature):
		raise InvalidDelivery('invalid signature')
	try:
		body = strict_json(raw)
		if not isinstance(body, dict):
			raise ValueError()
		for key in ('installation', 'repository'):
			value = body[key]['id']
			if type(value) is not int or value != binding[key+'_id']:
				raise ValueError()
		delivery_id = headers.get('x-github-delivery', '')
		event = headers.get('x-github-event', '')
		action = body.get('action', '')
		for value in (delivery_id, event):
			if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value):
				raise ValueError()
		if not isinstance(action, str) or not re.fullmatch(r'[a-z_]{0,64}', action):
			raise ValueError()
		return Delivery(1, binding['app_id'], binding['installation_id'], binding['repository_id'],
						delivery_id, hashlib.sha256(raw).hexdigest(), event, action, body, raw)
	except (ValueError, KeyError, TypeError, RecursionError, UnicodeError) as exc:
		raise InvalidDelivery('invalid envelope or source binding') from exc
