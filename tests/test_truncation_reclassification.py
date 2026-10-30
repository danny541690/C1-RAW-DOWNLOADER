import copy,unittest
from scripts.v093_reclassify_truncation import reclassify
class TruncationReclassificationTests(unittest.TestCase):
 def state(self):return dict(hold='IncompleteRead',tasks={'x':dict(status='SOURCE_HOLD',attempts=2,owner=None,error=dict(phase='FETCH',code='IncompleteRead'))})
 def test_preserves_budget_and_delays_retry_without_acceptance(self):
  s=self.state();self.assertEqual(reclassify(s,100),1);self.assertNotIn('hold',s);self.assertEqual(s['tasks']['x']['attempts'],2);self.assertEqual(s['tasks']['x']['next_at'],160);self.assertEqual(s['tasks']['x']['status'],'RETRY_WAIT');self.assertEqual(reclassify(s,200),0)
 def test_four_attempts_stay_blocked(self):
  s=self.state();s['tasks']['x']['attempts']=4;reclassify(s,0);self.assertEqual(s['tasks']['x']['status'],'BLOCKED')
 def test_other_holds_saved_bytes_and_active_owners_cannot_be_released(self):
  s=self.state();s['hold']='HTTPError_403';before=copy.deepcopy(s);self.assertEqual(reclassify(s,0),0);self.assertEqual(s,before)
  for change in [dict(owner='live'),dict(save_intent={'locator':'saved'}),dict(raw_reference='raw'),dict(error=dict(phase='VALIDATE',code='IncompleteRead'))]:
   s=self.state();s['tasks']['x'].update(change)
   with self.assertRaises(ValueError):reclassify(s,0)
