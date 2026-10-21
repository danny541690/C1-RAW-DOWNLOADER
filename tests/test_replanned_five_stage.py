import collections,io,json,unittest,zipfile
from unittest.mock import patch,Mock
from scripts import v093_replanned_five_stage as plan

class ReplanTests(unittest.TestCase):
    def test_independent_scopes_and_real_legacy_index(self):
        self.assertEqual((plan.RAW_MONTHS[0],plan.RAW_MONTHS[-1],len(plan.RAW_MONTHS)),('2014-04','2000-01',172))
        self.assertEqual((plan.AUDIT_MONTHS[0],plan.AUDIT_MONTHS[-1],len(plan.AUDIT_MONTHS)),('2026-10','2000-01',322))
        self.assertEqual(plan.LEGACY_MONTHS[11],'2014-04')
        self.assertNotIn('2026-10',plan.RAW_MONTHS)
    def test_resume_backs_up_recent_scan_and_adopts_old_checkpoint(self):
        w=object.__new__(plan.Worker);w.cursor={'run':plan.base.RUN,'month_index':4};w.d=Mock();w.d.find.return_value={'id':'old'};w.stagectrl='raw';w.owned=lambda:None;w.save_cursor=Mock()
        with patch.object(plan.engine,'getj',return_value={'version':plan.PLAN['legacy_checkpoint_namespace'],'month_index':11,'finished_months':[{'month':'2014-05'}]}):w.initialize_history_cursor()
        self.assertEqual(w.cursor['month_index'],0);self.assertEqual(w.cursor['raw_history_start'],'2014-04');w.save_cursor.assert_called_once()
        snapshot=json.loads(w.d.put.call_args.args[2]);self.assertEqual(snapshot['old_live_cursor']['month_index'],4)
    def test_wrong_legacy_checkpoint_fails_before_cursor_change(self):
        w=object.__new__(plan.Worker);w.cursor={'month_index':4};w.d=Mock();w.d.find.return_value={'id':'old'}
        with patch.object(plan.engine,'getj',return_value={'version':plan.PLAN['legacy_checkpoint_namespace'],'month_index':12}):
            with self.assertRaisesRegex(ValueError,'AUTHORIZED_201404'):w.initialize_history_cursor()
        self.assertEqual(w.cursor['month_index'],4);w.d.put.assert_not_called()
    def test_already_migrated_cursor_is_not_reset(self):
        w=object.__new__(plan.Worker);w.cursor={'execution_plan':plan.REVISION,'month_index':7};w.initialize_history_cursor();self.assertEqual(w.cursor['month_index'],7)
    def test_attempts_survive_old_namespace_migration(self):
        target={'attempt_ledger':{'units':{'a':2}}};old={'attempt_ledger':{'units':{'a':3,'b':4}},'units':{'c':{'attempts':2}}}
        plan.merge_attempts(target,old);self.assertEqual(target['attempt_ledger']['units'],{'a':3,'b':4,'c':2})
    def test_history_refuses_recent_dates_and_protects_saved_old_receipts(self):
        w=object.__new__(plan.Worker);w.phase='HISTORY_DOWNLOAD';w.state={'units':{},'protected_legacy_receipts':{}};w.save_state=Mock()
        with self.assertRaisesRegex(ValueError,'OUTSIDE_201404'):w.fetch_job({'month':'2026-10'},'units')
        job={'source':'TWSE','category':'prices','period':'2014-04-01','month':'2014-04'};k=plan.engine.key(job);w.state['protected_legacy_receipts'][k]={'sha256':'a'*64}
        with patch.object(plan.native,'request') as request:w.fetch_job(job,'units');request.assert_not_called()
        self.assertEqual(w.state['units'][k]['status'],'LEGACY_RECEIPT_RECONCILIATION_HOLD')
    def test_archive_is_read_once_but_each_member_hash_is_checked(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('a.raw',b'A');z.writestr('b.raw',b'B')
        cache=plan.ArchiveCache();a={'evidence_file':'file/a.raw','sha256':plan.native.sha(b'A')};c={'evidence_file':'file/b.raw','sha256':plan.native.sha(b'B')}
        with patch.object(plan.native,'read',return_value=b.getvalue()) as read:
            self.assertEqual(plan.cached_payload(None,a,cache)[0],b'A');self.assertEqual(plan.cached_payload(None,c,cache)[0],b'B');self.assertEqual(read.call_count,1)
            c['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):plan.cached_payload(None,c,cache)
    def test_newest_actual_content_date_precedes_old_insertion_order(self):
        a={'unit_id':'a','category':'prices','period':'2026-10-01','status':'SAVED_BASIC_VERIFIED','evidence_file':'x/a'}
        b=dict(a,unit_id='b',period='2026-10-21');self.assertEqual([e['unit_id'] for e in plan.newest_receipts({'units':{'a':a,'b':b}})],['b','a'])

    def test_longer_consumer_budgets_fit_one_hour_single_slot(self):
        budget=plan.PLAN['worker_budgets_minutes']
        self.assertEqual(sum(budget[s] for s in ('QA1','PRICE','FINANCIAL','CHIP')),52)
        starts=[0,20,34,46,60]
        for i,stage in enumerate(('QA1','PRICE','FINANCIAL','CHIP')):
            self.assertGreater(budget[stage],4)
            self.assertLessEqual(starts[i]+budget[stage]+2,starts[i+1])
