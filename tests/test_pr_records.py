"""Finite host-record budgets preserve canonical UTF-8 identity."""
import hashlib
import math
import unittest
from unittest.mock import patch

from task_tower.pr_policy import canonical
try:
    from task_tower.pr_records import canonical_record_identity, check_review_record_budget, MAX_RECORD_BYTES
except ImportError:
    canonical_record_identity=check_review_record_budget=None
    MAX_RECORD_BYTES=None


class RecordBudgetTests(unittest.TestCase):
    def test_utf8_identity_matches_existing_canonical_format(self):
        self.assertIsNotNone(canonical_record_identity,'Missing bounded host-record utility')
        value={'unicode':'\u00b9\u0412\U0001f600','nested':[1,True,None,{'b':2,'a':1}]}
        raw=canonical(value).encode('utf-8')
        self.assertEqual(canonical_record_identity(value,len(raw)),(len(raw),hashlib.sha256(raw).hexdigest()))
        with self.assertRaises(ValueError): canonical_record_identity(value,len(raw)-1)

    def test_nonfinite_and_nonpositive_limits_refused(self):
        self.assertIsNotNone(canonical_record_identity)
        for value in (math.nan,math.inf,-math.inf):
            with self.subTest(value=value),self.assertRaises(ValueError): canonical_record_identity({'v':value})
        for limit in (True,False,0,-1,1.5,'100'):
            with self.subTest(limit=limit),self.assertRaises(ValueError): canonical_record_identity({},limit)

    def test_exact_verified_record_reserve_boundary(self):
        self.assertIsNotNone(check_review_record_budget)
        self.assertEqual(MAX_RECORD_BYTES,536870912)
        request={'request':'\u00b9'}; provenance={'locator':'private'}
        from task_tower.pr_review import MAX_RESULT_BYTES
        expected=2*len(canonical(request).encode('utf-8'))+len(canonical(provenance).encode('utf-8'))+2*MAX_RESULT_BYTES+65536
        with patch('task_tower.pr_records.MAX_RECORD_BYTES',expected):
            self.assertEqual(check_review_record_budget(request,provenance),expected)
        with patch('task_tower.pr_records.MAX_RECORD_BYTES',expected-1),self.assertRaises(ValueError):
            check_review_record_budget(request,provenance)
