import copy,unittest
from scripts.v093_finalize_handoff_catalogs import filter_rows
class FinalizeTests(unittest.TestCase):
 def row(self,key='a',attempts=4):return dict(definition=dict(source='TWSE',key=key,period='2000-01-03'),attempts=attempts,status='READY_CHECK',execution_contract=dict(reference='old',sha256='a'*64),legacy_review={'provenance':['preserve']})
 def evidence(self):return dict(period='2000-01-03',reference='old',sha256='a'*64)
 def test_only_evidence_bound_held_row_is_excluded(self):
  rows=[self.row(),self.row('b')];before=copy.deepcopy(rows);kept,removed=filter_rows('TWSE',rows,{('TWSE','a'):self.evidence()})
  self.assertEqual([r['definition']['key'] for r in kept],['b']);self.assertEqual(kept[0]['attempts'],4);self.assertEqual(rows,before);self.assertEqual(len(removed),1)
 def test_changed_sha_or_period_cannot_remove_an_unrelated_original(self):
  for field in ('sha256','period','reference'):
   e=self.evidence();e[field]='different'
   with self.assertRaisesRegex(ValueError,'BINDING'):filter_rows('TWSE',[self.row()],{('TWSE','a'):e})
 def test_other_source_evidence_does_not_change_candidates(self):
  rows=[self.row()];kept,removed=filter_rows('TWSE',rows,{('TPEx','a'):self.evidence()});self.assertEqual(kept,rows);self.assertEqual(removed,[])
