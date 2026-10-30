import copy,unittest
from scripts.v093_action_catalogs import promotion_row,tdcc_missing_rows
class ActionTests(unittest.TestCase):
 def review(self,key='TDCC|2025-12|20251205|8400'):
  return dict(source='TDCC',task_key=key,attempts=3,action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE',provenance=[dict(source='TDCC',period='2025-12-05',legacy_unit_id='20251205|8400',status='UNRESOLVED')])
 def proof(self):return dict(official_evidence_id='fixture-menu',official_menu=dict(url='https://www.tdcc.com.tw/portal/zh/smWeb/qryStock',sha256='b'*64,offered_dates=['20251205']))
 def test_missing_query_preserves_last_source_attempt_and_does_not_assert_availability(self):
  item=self.review();rows=tdcc_missing_rows({item['task_key']:item},self.proof(),set());self.assertEqual(len(rows),1);self.assertEqual(rows[0]['attempts'],3);self.assertFalse(rows[0]['execution_contract']['missing_evidence']['availability_verified'])
 def test_existing_unit_empty_or_exhausted_is_not_downloaded(self):
  item=self.review();key=item['task_key']
  self.assertEqual(tdcc_missing_rows({key:item},self.proof(),{('20251205','8400')}),[])
  for change in ('ref','empty','exhausted'):
   changed=copy.deepcopy(item)
   if change=='ref':changed['provenance'][0]['raw_reference']='old'
   elif change=='empty':changed['provenance'][0]['status']='SKIPPED_SOURCE_EMPTY'
   else:changed['attempts']=4
   self.assertEqual(tdcc_missing_rows({key:changed},self.proof(),set()),[])
 def test_promotion_replaces_check_contract_without_losing_provenance(self):
  item=self.review();item.update(action='VERIFY_RETAINED_RAW_FIRST',attempts=4);item['provenance'][0].update(raw_reference='qa',sha256='a'*64);key=item['task_key']
  row=dict(definition=dict(source='TDCC',key=key,period='2025-12-05',slot='ASC'),status='READY_CHECK',attempts=4,legacy_review=item,execution_contract=dict(source='TDCC',key=key,period='2025-12-05',mode='RETAINED',date='20251205',code='8400',reference='qa',sha256='a'*64))
  p=promotion_row(row,'verified-fixture');self.assertEqual(p['attempts'],4);self.assertTrue(p['local_only']);self.assertEqual(p['status'],'READY');self.assertEqual(p['legacy_review'],item);self.assertEqual(p['execution_contract']['mode'],'PROMOTE')
