import unittest
from scripts.v093_legacy_handoff import normalize,inspect
class HandoffTests(unittest.TestCase):
 def test_native_tdcc_eight_digit_date_is_not_lost(self):
  rows,issues=normalize({'history_receipts':{'20251031|2330':dict(date='20251031',status='SAVED_BASIC_VERIFIED',attempts=1)}},'TDCC/HISTORY_20251031.json','TDCC')
  self.assertEqual(issues,[]);self.assertEqual(rows[0]['period'],'2025-10-31')
 def test_snapshot_capture_does_not_claim_content_period(self):
  rows,issues=normalize({'receipts':{'2026-10-23|/v1/opendata/2-12':dict(date=None,status='SAVED_BASIC_VERIFIED',content_period={'min':None,'max':None})}},'TDCC/CURSOR.json','TDCC')
  self.assertEqual(issues,[]);self.assertEqual(rows[0]['period_basis'],'SNAPSHOT_CAPTURE_DATE_ONLY')
  self.assertIsNone(rows[0]['content_period']['min'])
 def test_derived_layer_kept_out_of_raw_source_queue(self):
  rows,issues=normalize({'units':{'derived':dict(stage='CHIP',raw_sha256='a'*64,status='SUPERSEDED_PROVENANCE_REVISION')}},'LIVE/CHIP/2026-10/MONTH_STATE.json')
  self.assertEqual(rows,[]);self.assertEqual(issues[0]['reason'],'EXCLUDED_DERIVED_RECORD')
 def test_embedded_finmind_gap_receipts_and_unknown_inflight_are_preserved(self):
  rows,issues=normalize({'finmind_units':{'gap':dict(source='TWSE',start_date='2026-10-01',status='FINMIND_REQUEST_INTENT',attempts=2,next_retry_at=1234)}},'LIVE/RAW/2026-10/MONTH_STATE.json')
  self.assertEqual(issues,[]);self.assertEqual(rows[0]['source'],'FinMind')
  self.assertEqual(rows[0]['retry_after_epoch'],1234)
  self.assertEqual(next(iter(inspect(rows)['tasks'].values()))['action'],'RECONCILE_INTERRUPTED_REQUEST')
 def test_official_member_reference_and_register_identity_preserved(self):
  rows,issues=normalize({'units':{'old':dict(source='TWSE',period='2026-10-01',unit_id='u',evidence_file='file/member.json',sha256='a'*64,attempts=3,status='SAVED_BASIC_VERIFIED')}},'LIVE/RAW/2026-10/MONTH_STATE.json')
  self.assertEqual(issues,[]);self.assertEqual(rows[0]['task_key'],'TWSE|2026-10|u')
  self.assertEqual(rows[0]['raw_reference'],'file/member.json')
  self.assertEqual(inspect(rows)['tasks'][rows[0]['task_key']]['action'],'VERIFY_RETAINED_RAW_FIRST')
 def test_tdcc_history_sidecar_is_not_lost_and_duplicate_receipts_do_not_reset(self):
  rows,issues=normalize({'history_receipts':{'20251031|2330':dict(status='REQUEST_INTENT',attempts=4)}},'TDCC/HISTORY_20251031.json','TDCC')
  self.assertEqual(issues,[]);self.assertEqual(rows[0]['period'],'2025-10-31')
  r=inspect(rows+rows);self.assertEqual(r['unique_tasks'],1)
  task=next(iter(r['tasks'].values()));self.assertEqual(task['attempts'],4)
  self.assertEqual(task['action'],'RECONCILE_INTERRUPTED_REQUEST');self.assertFalse(task['download_authorized'])
 def test_ndc_native_month_and_conflicts_are_quarantined(self):
  rows,_=normalize({'receipts':{'2026-08':dict(file_id='f',sha256='a'*64,status='SAVED_RAW_ROWS_READBACK_VERIFIED')}},'NDC/CURSOR.json','NDC')
  other=dict(rows[0],sha256='b'*64);self.assertEqual(len(inspect(rows+[other])['version_conflicts']),1)
 def test_unknown_period_is_not_guessed_from_current_date(self):
  rows,issues=normalize({'receipts':{'snapshot':dict(file_id='f',status='SAVED_BASIC_VERIFIED')}},'TDCC/CURSOR.json','TDCC')
  self.assertEqual(rows,[]);self.assertEqual(issues[0]['reason'],'PERIOD_UNPROVEN')
