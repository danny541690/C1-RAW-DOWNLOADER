import copy,time,unittest,collections
from unittest.mock import patch,Mock
from scripts import v093_repair_execution as e
from scripts.v093_official_repair import RepairWorker
from tests.test_stage06_financial_repair import sample

class ReparseExecutionTests(unittest.TestCase):
    def job(self):return dict(source='MOPS',category='CashflowStatement',period='2023-03-31',unit_id='test-unit')
    def test_real_transform_write_readback_and_receipt_keep_raw(self):
        raw=sample();before=bytes(raw);store={}
        receipt=e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,
                                  lambda n,b:store.setdefault(n,b),lambda n:store[n])
        self.assertEqual(raw,before);self.assertEqual(receipt['evidence']['cells_compared'],3)
        self.assertTrue(receipt['remote_readback_hash_verified']);self.assertFalse(receipt['complete'])
        self.assertFalse(receipt['numeric_verified']);self.assertFalse(receipt['pit_verified'])
        self.assertEqual(receipt['raw_sha256'],e.digest(raw))
    def test_input_hash_mismatch_never_writes(self):
        write=Mock()
        with self.assertRaisesRegex(ValueError,'INPUT_SHA'):
            e.reparse_financial(sample(),self.job(),'bad',lambda:None,write,lambda n:b'')
        write.assert_not_called()
    def test_source_missing_company_is_not_a_parser_success(self):
        raw=sample();write=Mock();job=dict(self.job(),codes=['2330','2317','9103'])
        with self.assertRaisesRegex(ValueError,'FINANCIAL_SOURCE_COMPANIES_MISSING:9103'):
            e.reparse_financial(raw,job,e.digest(raw),lambda:None,write,lambda n:b'')
        write.assert_not_called()
    def test_wrong_remote_output_never_returns_verified_receipt(self):
        raw=sample()
        with self.assertRaisesRegex(ValueError,'READBACK_SHA'):
            e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,lambda *a:None,lambda n:b'corrupt')
    def test_expired_writer_cannot_publish_receipt(self):
        raw=sample();store={};calls=[]
        def owned():
            calls.append(1)
            if len(calls)==3:raise RuntimeError('FENCE_EXPIRED')
        with self.assertRaisesRegex(RuntimeError,'FENCE_EXPIRED'):
            e.reparse_financial(raw,self.job(),e.digest(raw),owned,lambda n,b:store.setdefault(n,b),lambda n:store[n])
    def test_retry_queue_keeps_cooldown_and_quality_separate(self):
        journal={'units':{'a':{'status':'UNRESOLVED_SOURCE_LIMIT','next_retry_at':100},
            'b':{'status':'LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS','terminal':True,'complete':False},
            'c':{'status':'CONTENT_CHECK_PASS','terminal':True,'complete':True}}}
        before=copy.deepcopy(journal);index={'2000-01':e.pending_month(journal)}
        self.assertEqual(e.due_months(index,99),[]);self.assertEqual(e.due_months(index,100),['2000-01'])
        self.assertEqual(index['2000-01']['retry_units'],1);self.assertEqual(index['2000-01']['blocked_units'],1)
        self.assertEqual(journal,before)
    def test_meeting_pause_does_not_disable_due_work(self):
        from tests.test_repair_prelaunch import MeetingTests
        w=MeetingTests().worker();w.until=time.monotonic()+600
        w.pending_index={'2000-02':{'next_retry_at':0}};captured=[]
        with patch('scripts.v093_official_repair.capture_history_month',side_effect=lambda w,m:captured.append(m)), \
             patch('scripts.v093_official_repair.claim_month',return_value=(False,{'status':'PAUSED_AT_MEETING'})), \
             patch('scripts.v093_official_repair.commit'):
            w.run()
        self.assertEqual(captured,['2000-02']);self.assertEqual(w.cursor['status'],'PAUSED_AT_MEETING')
    def integration_worker(self):
        from scripts import v093_official_repair as r
        raw=sample();job=dict(self.job(),month='2023-03',report_period='20231',codes=['2330','2317'],url='https://mopsfin.twse.com.tw/compare/report')
        key=r.engine.key(job);old=dict(job,status='SAVED_BASIC_VERIFIED',sha256=e.digest(raw),evidence_file='raw/member')
        w=object.__new__(RepairWorker);w.state={'financial_units':{key:copy.deepcopy(old)}}
        w.journal={'month':'2023-03','units':{}};w.checked=w.repaired=w.downloaded=0
        w.circuit=collections.Counter();w.source_requests=collections.Counter();w.until=time.monotonic()+300
        w.cache=None;w.monthctrl='month';w.save_journal=Mock();w.save_state=Mock();w.owned=Mock();files={}
        w.d=type('Drive',(),{'folder':lambda *a:'isolated','put':lambda self,p,n,b,*a,**kw:files.setdefault(n,b),'read':lambda self,p,n:files[n]})()
        return r,w,raw,job,key,old
    def test_worker_executes_reparse_without_raw_replacement_or_source_call(self):
        r,w,raw,job,key,old=self.integration_worker()
        with patch.object(r,'cached_payload',return_value=(raw,'archive')), \
             patch.object(r,'validate_content',return_value={'rows':2,'codes':['2330','2317'],'row_audit':{'unverified':['ACCOUNTING_AND_PIT']}}), \
             patch.object(r.native,'request') as source:
            w.repair_one(job,'financial_units',[{'kind':'PARSER_OR_SEMANTIC_CORRECTION_REQUIRED'}])
        source.assert_not_called();self.assertEqual(w.state['financial_units'][key],old)
        row=w.journal['units'][key];self.assertTrue(row['reparse_receipt']['remote_readback_hash_verified'])
        self.assertEqual(row['next_action'],'VERIFY_ACCOUNTING_UNITS_AND_PIT');self.assertFalse(row['complete'])
    def test_worker_reparse_failure_does_not_redownload_valid_raw(self):
        r,w,raw,job,key,old=self.integration_worker();w.d.read=lambda *a:b'corrupt'
        with patch.object(r,'cached_payload',return_value=(raw,'archive')), \
             patch.object(r,'validate_content',return_value={'rows':2,'codes':['2330','2317'],'row_audit':{'unverified':['PIT']}}), \
             patch.object(r.native,'request') as source:
            w.repair_one(job,'financial_units',[])
        source.assert_not_called();self.assertEqual(w.state['financial_units'][key],old)
        self.assertEqual(w.journal['units'][key]['status'],'LOCAL_REPARSE_FAILED')

if __name__=='__main__':unittest.main()
