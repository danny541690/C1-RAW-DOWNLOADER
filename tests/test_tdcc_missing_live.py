import copy,unittest
from scripts.v093_tdcc_missing_live import select
class MissingSelectionTests(unittest.TestCase):
 def row(self,key,date,code='2330',attempts=1,status='UNRESOLVED',ref=None):
  return dict(source='TDCC',attempts=attempts,action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE',provenance=[dict(legacy_unit_id=date+'|'+code,status=status,raw_reference=ref)])
 def test_unique_head_tail_only_from_offered_menu(self):
  tasks={str(i):self.row(str(i),date) for i,date in enumerate(['20251031','20261023','20261016'])}
  jobs=select(dict(tasks=tasks),['20261016','20261023'])
  self.assertEqual([j['date'] for j in jobs],['20261023','20261016']);self.assertEqual([j['slot'] for j in jobs],['DESC','ASC'])
 def test_success_empty_retained_exhausted_and_interrupted_never_refetched(self):
  for status,attempts,ref in [('SAVED_BASIC_VERIFIED',1,None),('SKIPPED_SOURCE_EMPTY',1,None),('UNRESOLVED',3,None),('UNRESOLVED',1,'old'),('REQUEST_INTENT',1,None)]:
   self.assertEqual(select(dict(tasks={'k':self.row('k','20261023',status=status,attempts=attempts,ref=ref)}),['20261023']),[])
 def test_one_case_not_duplicated_and_any_retained_version_blocks(self):
  row=self.row('k','20261023');self.assertEqual(len(select(dict(tasks={'k':row}),['20261023'])),1)
  row['provenance'].append(dict(row['provenance'][0],raw_reference='retained'))
  self.assertEqual(select(dict(tasks={'k':row}),['20261023']),[])
