"""Conservative arithmetic only, never host sample or claim authority."""
import unittest
from task_tower.group_policy import ROLES
try:
    from task_tower.group_resources import task_envelope,resource_budget,resources_fit
except ImportError:
    task_envelope=resource_budget=resources_fit=None


class GroupResourceMathTests(unittest.TestCase):
    def setUp(self):
        self.capacity=dict(mode='auto',max_executors=None,max_inflight=None,
            max_cpu_millis=None,max_memory_bytes=None,fallback=None)
        self.roles={role:role for role in ROLES}
        self.grants={role:dict(pool_id='approved',cpu_millis=1000,memory_bytes=1024**3,max_parallel=None)
            for role in ROLES}

    def available(self): self.assertTrue(callable(task_envelope),'Missing conservative resource arithmetic')

    def test_envelope_is_maximum_of_six_plus_fixed_helper_overhead(self):
        self.available(); self.grants['spec_reviewer']['cpu_millis']=2400
        self.grants['test_executor']['memory_bytes']=3*1024**3
        value=task_envelope(self.roles,self.grants)
        self.assertEqual(value['cpu_millis'],2500); self.assertEqual(value['memory_bytes'],3*1024**3+64*1024**2)
        self.assertEqual(value['role_pools'],{role:'approved' for role in ROLES})

    def test_available_budget_reserves_headroom_and_uses_explicit_minima(self):
        self.available()
        value=resource_budget(8000,16*1024**3,self.capacity)
        self.assertEqual(value['cpu_millis'],7000); self.assertEqual(value['memory_bytes'],15*1024**3)
        capped=resource_budget(8000,16*1024**3,dict(self.capacity,max_cpu_millis=500,max_memory_bytes=123))
        self.assertEqual(capped['cpu_millis'],500); self.assertEqual(capped['memory_bytes'],123)
        zero=resource_budget(500,100,self.capacity)
        self.assertEqual((zero['cpu_millis'],zero['memory_bytes']),(0,0))

    def test_missing_measurements_need_explicit_fallback_and_never_raise_known_values(self):
        self.available(); self.assertEqual(resource_budget(None,100,self.capacity)['status'],'unavailable')
        fallback=dict(cpu_millis=9000,memory_bytes=16*1024**3,max_executors=3)
        value=resource_budget(None,2*1024**3,dict(self.capacity,max_executors=2,fallback=fallback))
        self.assertEqual(value['status'],'fallback'); self.assertEqual(value['max_executors'],2)
        self.assertEqual(value['memory_bytes'],1024**3)
        known=resource_budget(0,0,dict(self.capacity,fallback=fallback))
        self.assertEqual(known['status'],'available'); self.assertEqual(known['cpu_millis'],0)
        self.assertIsNone(known['max_executors'])

    def test_arithmetic_allows_three_when_resources_fit_without_synthesizing_count_cap(self):
        self.available(); envelope=task_envelope(self.roles,self.grants)
        budget=resource_budget(8000,16*1024**3,self.capacity)
        held=[]
        for _ in range(3):
            self.assertTrue(resources_fit(budget,held,envelope)); held.append(envelope)
        self.assertTrue(resources_fit(budget,held,envelope))
        self.assertFalse(resources_fit(resource_budget(3000,16*1024**3,self.capacity),held,envelope))

    def test_unknown_held_resources_and_either_dimension_block(self):
        self.available(); envelope=task_envelope(self.roles,self.grants)
        budget=resource_budget(8000,16*1024**3,self.capacity)
        self.assertFalse(resources_fit(budget,[None],envelope))
        self.assertFalse(resources_fit(dict(budget,cpu_millis=100),[],envelope))
        self.assertFalse(resources_fit(dict(budget,memory_bytes=100),[],envelope))
        self.assertFalse(resources_fit(resource_budget(None,None,self.capacity),[],envelope))

    def test_explicit_count_cap_and_fallback_cap_narrow_resource_feasibility(self):
        self.available(); envelope=task_envelope(self.roles,self.grants)
        budget=resource_budget(16000,32*1024**3,dict(self.capacity,max_executors=3))
        self.assertTrue(resources_fit(budget,[envelope,envelope],envelope))
        self.assertFalse(resources_fit(budget,[envelope]*3,envelope))
        fallback=dict(cpu_millis=16000,memory_bytes=32*1024**3,max_executors=1)
        budget=resource_budget(None,32*1024**3,dict(self.capacity,fallback=fallback))
        self.assertTrue(resources_fit(budget,[],envelope))
        self.assertFalse(resources_fit(budget,[envelope],envelope))

    def test_malformed_arithmetic_shapes_have_closed_valueerror(self):
        self.available(); envelope=task_envelope(self.roles,self.grants)
        budget=resource_budget(8000,16*1024**3,self.capacity)
        for held,candidate in (([],{}),([{}],envelope)):
            with self.assertRaises(ValueError): resources_fit(budget,held,candidate)
        with self.assertRaises(ValueError): resources_fit(dict(status='available'),[],envelope)

    def test_boolean_negative_overflow_missing_role_or_grant_refuse(self):
        self.available()
        for cpu in (True,-1,2**63):
            with self.subTest(cpu=cpu),self.assertRaises(ValueError): resource_budget(cpu,1024**3,self.capacity)
        for roles in ({},dict(self.roles,extra='spec_executor')):
            with self.assertRaises(ValueError): task_envelope(roles,self.grants)
        grants=dict(self.grants); grants.pop('spec_executor')
        with self.assertRaises(ValueError): task_envelope(self.roles,grants)
        grants=dict(self.grants,spec_executor=dict(self.grants['spec_executor'],cpu_millis=2**63-1))
        with self.assertRaises(ValueError): task_envelope(self.roles,grants)
        budget=resource_budget(2**63-1,2**63-1,self.capacity)
        huge=dict(cpu_millis=2**63-1,memory_bytes=2**63-1)
        with self.assertRaises(ValueError): resources_fit(budget,[huge,huge],huge)
