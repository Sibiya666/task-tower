"""Bounded private PR-record encoding; hashes alone never grant process proof.

Strict journal-backed record readers are a separate implementation step.
"""
import hashlib
import json

from .pr_review import MAX_RESULT_BYTES

MAX_RECORD_BYTES=536870912


def canonical_record_identity(value,limit=None):
    """Count/hash existing canonical UTF-8 without a second complete JSON copy."""
    if limit is None: limit=MAX_RECORD_BYTES
    if type(limit) is not int or not 0<limit<=MAX_RECORD_BYTES:
        raise ValueError('Invalid private PR record limit')
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    count=0; digest=hashlib.sha256()
    try:
        for chunk in encoder.iterencode(value):
            # JSONEncoder may yield one large string token. Bound each UTF-8
            # conversion, including non-BMP characters, without changing bytes.
            for start in range(0,len(chunk),65536):
                raw=chunk[start:start+65536].encode('utf-8')
                count+=len(raw)
                if count>limit: raise ValueError('Private PR record limit exceeded')
                digest.update(raw)
    except (TypeError,OverflowError,RecursionError,UnicodeError):
        raise ValueError('Invalid private PR record encoding') from None
    return count,digest.hexdigest()


def check_review_record_budget(request,provenance):
    """Reserve before admission/launch; actual records still need own bounds."""
    size,_=canonical_record_identity(request)
    provenance_size,_=canonical_record_identity(provenance)
    reserve=2*size+provenance_size+2*MAX_RESULT_BYTES+65536
    if reserve>MAX_RECORD_BYTES: raise ValueError('Private PR review record budget exceeded')
    return reserve
