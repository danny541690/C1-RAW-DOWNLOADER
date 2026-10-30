import copy,unittest
from scripts.v093_missing_rules import eligibility,make_row,official_job
class MissingRulesTests(unittest.TestCase):
 def inputs(self,source='TWSE',category='prices_indices',period='2026-09-01'):
  origin=dict(file_id='official-ledger',version='1',sha256='a'*64);key=source+'|'+period[:7]+'|unit'
  row=dict(source=source,task_key=key,period=period,legacy_unit_id='unit')
  item=dict(source=source,task_key=key,attempts=2,action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE',provenance=[dict(period=period,status='WAIT_SHARED_SOURCE_WINDOW',legacy_unit_id='unit',ledger_origin=origin)])
  return item,row,dict(category=category),{},origin
 def test_query_preserves_attempts_and_never_certifies_availability(self):
  args=self.inputs();r,reason=make_row(*args);self.assertIsNone(reason);self.assertEqual(r['attempts'],2);self.assertFalse(r['execution_contract']['missing_evidence']['availability_verified']);self.assertFalse(r['full_acceptance'])
 def test_any_prior_empty_or_interrupted_version_prevents_download(self):
  for status in ['SOURCE_NO_DATA_UNCONFIRMED','REQUEST_INTENT','NO_ROWS_RETURNED_NOT_COVERAGE','OFFICIAL_PERIOD_NOT_PROVIDED','SKIPPED_SOURCE_EMPTY','RAW_SAVED']:
   item,*_=self.inputs();item['provenance'].append(dict(status=status,period='2026-09-01'));self.assertIsNotNone(eligibility(item))
 def test_old_raw_exhaustion_and_period_conflict_block(self):
  for change in ['raw','attempts','period']:
   item,*_=self.inputs()
   if change=='raw':item['provenance'][0]['raw_reference']='already-saved'
   elif change=='attempts':item['attempts']=4
   else:item['provenance'].append(dict(period='2026-08-01',status='UNRESOLVED'))
   self.assertIsNotNone(eligibility(item))
 def test_foreign_ledger_cannot_authorize_query(self):
  args=list(self.inputs());args[-1]=dict(file_id='other',version='1',sha256='b'*64);self.assertEqual(make_row(*args)[1],'LEDGER_REVIEW_BINDING')
 def test_only_supported_prices_and_completed_revenue_routes(self):
  self.assertIsNone(official_job('TWSE','2000-01-03','prices_indices'))
  self.assertIsNone(official_job('TWSE','2026-09-01','institutional'))
  self.assertIsNone(official_job('MOPS','2099-01','revenue_sii_0'))
  for args in [self.inputs('TPEx','prices'),self.inputs('MOPS','revenue_sii_0','2026-09')]:self.assertIsNone(make_row(*args)[1])
 def test_ndc_unpublished_and_finmind_without_alignment_are_held(self):
  self.assertEqual(make_row(*self.inputs('NDC','business','2026-09'))[1],'VERIFIED_ARCHIVE_MONTH_REQUIRED')
  self.assertEqual(make_row(*self.inputs('FinMind','prices','2026-09'))[1],'OFFICIAL_GAP_ALIGNMENT_REQUIRED')
 def test_forged_query_route_is_rejected_by_native_adapter(self):
  from scripts.v093_source_adapters import NativeAdapter
  r,_=make_row(*self.inputs());r['execution_contract']['missing_evidence']['native_route']['url']='https://example.com/'
  with self.assertRaisesRegex(ValueError,'OFFICIAL_QUERY_ROUTE_OR_LEDGER_BINDING'):NativeAdapter(None,None,dict(source='TWSE',key=r['definition']['key']),r)
