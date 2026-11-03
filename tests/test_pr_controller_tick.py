"""Control-flow probes only; these doubles grant no effect authority."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from task_tower.pr_worker import Controller, step
from task_tower.pr_journal import PRJournal


class ControllerTickTests(unittest.TestCase):
    def test_uncertain_action_stops_tick_and_next_tick_advances_cursor(self):
        journal=object.__new__(PRJournal);journal._active='owner'
        controller=object.__new__(Controller)
        controller.journal=journal;controller.owner_id='owner';controller.cursor=0
        controller.references=(('owner/repo',1),('owner/repo',2))
        controller.context=SimpleNamespace(_fresh_inputs=lambda:{'policy':{'max_prs_per_tick':2}})
        visited=[]
        def advance(task):
            visited.append(task['pr_number'])
            if task['pr_number']==1:raise ValueError('Lost response after consumed intent')
            return {'status':'idle'},False
        with patch('task_tower.pr_worker.authorized_task',side_effect=lambda p,r,n:{'repository':r,'pr_number':n}),patch.object(PRJournal,'get',return_value=None),patch.object(Controller,'_advance',side_effect=advance):
            report=step({'_controller':controller},journal,owner_id='owner')
            self.assertEqual(visited,[1])
            self.assertEqual(report['reason'],'pr_step_unverified')
            step({'_controller':controller},journal,owner_id='owner')
            self.assertEqual(visited,[1,2,1])
