"""Portable FFI fault fixtures; these are not actual native qualification."""
import ctypes
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from task_tower.group_resources import _windows_probe,_ProbeDeadline


class GroupResourceNativeShapeTests(unittest.TestCase):
    def probe(self,*,active=8,process_mask=15,system_mask=255,in_job=False,failure=None,bad_memory=False):
        calls=[]
        def wrap(name,action):
            def function(*args):
                calls.append(name)
                return 0 if name==failure else action(*args)
            return function
        def affinity(handle,process,system):
            self.assertEqual(handle.value,ctypes.c_void_p(-1).value)
            process._obj.value=process_mask; system._obj.value=system_mask; return 1
        def memory(value):
            value=value._obj; self.assertEqual(value.length,64)
            for key,total,available in (('physical',16,8),('commit',32,6),('virtual',64,4)):
                setattr(value,'total_'+key,total*1024**3); setattr(value,'available_'+key,available*1024**3)
            if bad_memory: value.available_physical=value.total_physical+1
            return 1
        def membership(process,job,result):
            self.assertIsNone(job); result._obj.value=int(in_job); return 1
        def query(job,kind,value,length,returned):
            self.assertIsNone(job); self.assertIn(kind,(9,15))
            self.assertEqual(length,ctypes.sizeof(value._obj)); returned._obj.value=length
            # All immediate limit flags deliberately remain zero. The unresolved
            # enclosing chain must still make CPU and memory unknown.
            return 1
        api=SimpleNamespace(
            GetActiveProcessorCount=wrap('GetActiveProcessorCount',lambda group:active),
            GetProcessAffinityMask=wrap('GetProcessAffinityMask',affinity),
            GlobalMemoryStatusEx=wrap('GlobalMemoryStatusEx',memory),
            IsProcessInJob=wrap('IsProcessInJob',membership),
            QueryInformationJobObject=wrap('QueryInformationJobObject',query))
        with patch('ctypes.WinDLL',return_value=api,create=True) as factory:
            result=_windows_probe(time.monotonic()+2)
        factory.assert_called_once_with('kernel32',use_last_error=True)
        return result,calls

    def test_affinity_and_conservative_available_memory_use_fixed_native_calls(self):
        (cpu,memory,limitations,provenance),calls=self.probe()
        self.assertEqual(cpu,4000); self.assertEqual(memory,4*1024**3); self.assertEqual(limitations,[])
        self.assertEqual(provenance['in_job'],False)
        self.assertEqual(calls,['GetActiveProcessorCount','GetProcessAffinityMask','GlobalMemoryStatusEx','IsProcessInJob'])

    def test_zero_immediate_job_limits_do_not_prove_enclosing_constraints(self):
        (cpu,memory,limitations,provenance),calls=self.probe(in_job=True)
        self.assertIsNone(cpu); self.assertIsNone(memory)
        self.assertIn('enclosing_job_constraints_unresolved',limitations)
        self.assertEqual(provenance['immediate_job_limits']['flags'],0)
        self.assertEqual(calls.count('QueryInformationJobObject'),2)

    def test_cpu_groups_mask_and_native_failures_are_unknown_not_minimum_one(self):
        for change in (dict(active=128),dict(process_mask=0),dict(system_mask=3),dict(failure='GetProcessAffinityMask')):
            with self.subTest(change=change):
                (cpu,memory,limitations,_),_=self.probe(**change)
                self.assertIsNone(cpu); self.assertIsNotNone(memory); self.assertIn('cpu_measurement_unavailable',limitations)
        (cpu,memory,limitations,_),_=self.probe(failure='IsProcessInJob')
        self.assertIsNone(cpu); self.assertIsNone(memory); self.assertIn('job_membership_unavailable',limitations)

    def test_inconsistent_or_failed_memory_is_unknown_and_job_queries_cannot_fill_it(self):
        for change in (dict(bad_memory=True),dict(failure='GlobalMemoryStatusEx')):
            with self.subTest(change=change):
                (cpu,memory,limitations,_),_=self.probe(**change)
                self.assertIsNotNone(cpu); self.assertIsNone(memory)
                self.assertIn('memory_measurement_unavailable',limitations)

    def test_expired_probe_has_no_native_call(self):
        calls=[]
        api=SimpleNamespace(**{name:(lambda *args: calls.append(args) or 1) for name in
            ('GetActiveProcessorCount','GetProcessAffinityMask','GlobalMemoryStatusEx','IsProcessInJob','QueryInformationJobObject')})
        with patch('ctypes.WinDLL',return_value=api,create=True),self.assertRaises(_ProbeDeadline):
            _windows_probe(time.monotonic()-1)
        self.assertEqual(calls,[])
