import datetime,subprocess,sys,unittest
from scripts.v093_five_stage_policy import load_policy,historical_months,bounded_month,unit_key,reuse_action,retry_action,finmind_eligible

class AdoptedFiveStagePolicyTests(unittest.TestCase):
    def test_descending_history_and_current_month_topup_boundary(self):
        today=datetime.date(2026,10,21)
        months=historical_months(today)
        self.assertEqual((len(months),months[0],months[-1]),(322,'2026-10','2000-01'))
        self.assertEqual(bounded_month('2026-10',today),('2026-10-01','2026-10-21'))
        self.assertEqual(bounded_month('2026-10',datetime.date(2026,10,22))[1],'2026-10-22')
        with self.assertRaises(ValueError):bounded_month('2026-11',today)

    def test_saved_source_cannot_hide_another_missing_source(self):
        digest='a'*64
        receipt={'database_version':'0.93','sha256':digest,**{k:True for k in ('durable_readback','source_identity_ok','date_identity_ok','security_identity_ok','basic_format_ok')}}
        self.assertEqual(reuse_action(receipt,digest,file_exists=True),'REUSE_SAVED_BASIC_UNIT')
        self.assertEqual(reuse_action(None,file_exists=False),'DOWNLOAD_MISSING_UNIT')
        self.assertEqual(reuse_action(None,file_exists=True),'VERIFY_EXISTING_FIRST')
        self.assertEqual(reuse_action(receipt,'b'*64,file_exists=True),'QUARANTINE_HASH_CONFLICT')
        self.assertEqual(reuse_action(dict(receipt,database_version='0.92'),digest),'BLOCK_LEGACY_OR_UNPROVEN_DATABASE')

    def test_source_market_dataset_and_period_are_distinct_units(self):
        unit=dict(source='TWSE',market='TSE',dataset='ohlc',period_start='2026-09-01',period_end='2026-09-01')
        for field,value in [('source','TPEx'),('market','OTC'),('dataset','institutional'),('period_end','2026-09-02')]:
            self.assertNotEqual(unit_key(unit),unit_key(dict(unit,**{field:value})))

    def test_initial_plus_three_retries_and_crash_reconciliation(self):
        self.assertEqual(load_policy()['retry']['max_total_attempts'],4)
        for count in (1,2,3):self.assertEqual(retry_action(count,'429'),'BACKOFF_AND_RETRY')
        self.assertEqual(retry_action(4,'429'),'QUEUE_REPAIR_AND_CONTINUE')
        self.assertEqual(retry_action(1,'SCHEMA_CHANGED'),'ISOLATE_AND_REPORT')
        self.assertEqual(retry_action(1,'UNKNOWN_AFTER_CRASH'),'RECONCILE_BEFORE_REPLAY')

    def test_finmind_requires_official_gap_and_semantic_evidence(self):
        gap=dict(official_source='MOPS',missing_unit_confirmed=True,official_evidence_sha256='a'*64,
                 **{k:True for k in ('definition_compatible','unit_compatible','sign_compatible','frequency_compatible','availability_compatible')})
        self.assertTrue(finmind_eligible(gap))
        for key in ('missing_unit_confirmed','definition_compatible','unit_compatible','sign_compatible','frequency_compatible','availability_compatible'):
            self.assertFalse(finmind_eligible(dict(gap,**{key:False})))
        self.assertFalse(finmind_eligible({}))

    def test_legacy_capture_clis_exit_before_missing_credentials_or_source_requests(self):
        for module in ('v093_raw_firstpass','v093_independent_raw','v093_history_reverse','v093_raw_2015_to_2000'):
            r=subprocess.run([sys.executable,'-m','scripts.'+module],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('LEGACY_WORKER_POLICY_NOT_INTEGRATED',r.stderr)

if __name__=='__main__':unittest.main()
