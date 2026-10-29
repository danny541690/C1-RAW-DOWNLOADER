import copy,hashlib,unittest
from scripts.v093_source_receipt_migration import migrate
from scripts.v093_tdcc_scope import build_scope,verify_scope

class MigrationTests(unittest.TestCase):
 def receipt(self,key='one',raw=b'good',**kw):
  row=dict(source='TDCC',task_key=key,attempts=2,status='SAVED_BASIC_VERIFIED',raw_reference='file',sha256=hashlib.sha256(raw).hexdigest());row.update(kw);return row
 def test_same_raw_reuses_after_actual_readback_and_keeps_max_attempts(self):
  calls=[]
  def read(ref):calls.append(ref);return b'good'
  r=migrate([self.receipt(),self.receipt(attempts=4)],read,'TDCC')
  self.assertEqual(r['counts'],dict(reusable=1,pending=0,blocked=0));self.assertEqual(calls,['file'])
  self.assertEqual(r['reusable']['one']['attempts'],4);self.assertFalse(r['reusable']['one']['full_acceptance'])
 def test_conflicting_versions_block_without_selecting_latest(self):
  r=migrate([self.receipt(),self.receipt(raw=b'other')],lambda _:self.fail('No arbitrary raw selection'),'TDCC')
  self.assertEqual(r['counts']['blocked'],1)
 def test_wrong_or_missing_bytes_do_not_pass(self):
  for raw in (b'wrong',None):
   r=migrate([self.receipt()],lambda _:raw,'TDCC');self.assertEqual(r['counts']['reusable'],0)
 def test_unfinished_receipts_preserve_attempts_and_are_not_downloaded(self):
  r=migrate([self.receipt(status='REQUEST_INTENT',attempts=4)],lambda _:self.fail('No read needed'),'TDCC')
  self.assertEqual(r['pending']['one']['attempts'],4);self.assertEqual(r['market_downloads'],0)
 def test_reference_failure_remains_visible_even_with_same_hash_good_copy(self):
  def read(ref):
   if ref=='bad':raise RuntimeError('do-not-store-secret-response')
   return b'good'
  r=migrate([self.receipt(raw_reference='bad'),self.receipt(raw_reference='good')],read,'TDCC')
  self.assertEqual(r['reusable']['one']['reference_errors'],['RuntimeError'])
  self.assertNotIn('secret',str(r))
 def test_source_isolation_and_attempt_schema(self):
  self.assertEqual(migrate([self.receipt(source='MOPS')],lambda _:b'good','TDCC')['total_tasks'],0)
  with self.assertRaises(ValueError):migrate([self.receipt(attempts=True)],lambda _:b'good','TDCC')

 def test_malformed_digest_is_recorded_as_blocked(self):
  r=migrate([self.receipt(sha256=[])],lambda _:b'good','TDCC')
  self.assertEqual(r['counts']['blocked'],1)

class ScopeTests(unittest.TestCase):
 def test_full_offered_menu_not_legacy_may_boundary(self):
  dates=['20251031','20260102','20260424','20260508','20261023']
  s=build_scope(dates,'2026-10-29')['scope'];verify_scope(s)
  self.assertEqual(set(s['owners']['ASC']+s['owners']['DESC']),set(dates))
  self.assertFalse(set(s['owners']['ASC'])&set(s['owners']['DESC']))
  self.assertFalse(s['historical_universe_complete'])
 def test_scope_does_not_shift_when_new_menu_dates_appear(self):
  s=build_scope(['20251031','20261023'],'2026-10-29')['scope']
  r=build_scope(['20251031','20261023','20261028'],'2026-10-29',s)
  self.assertEqual(r['scope'],s);self.assertEqual(r['new_dates_pending'],['20261028'])
 def test_removed_dates_are_not_forgotten_or_marked_complete(self):
  s=build_scope(['20251031','20261023'],'2026-10-29')['scope']
  r=build_scope(['20261023'],'2026-10-29',s)
  self.assertEqual(r['old_dates_no_longer_in_menu'],['20251031'])
 def test_future_and_invalid_dates_and_tampering(self):
  self.assertEqual(build_scope(['20261030'],'2026-10-29')['outside_campaign'],['20261030'])
  with self.assertRaises(ValueError):build_scope(['20260230'],'2026-10-29')
  s=build_scope(['20251031'],'2026-10-29')['scope'];s['owners']['ASC']=['20251031']
  with self.assertRaises(ValueError):verify_scope(s)

 def test_rehashed_future_scope_is_still_rejected(self):
  import json
  s=build_scope(['20251031'],'2026-10-29')['scope'];s['owners']['DESC']=['20261030']
  body=dict(s);body.pop('scope_id');s['scope_id']=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
  with self.assertRaises(ValueError):verify_scope(s)
