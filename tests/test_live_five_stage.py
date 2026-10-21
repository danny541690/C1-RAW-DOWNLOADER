import io,json,unittest,urllib.error,zipfile
from unittest.mock import patch
from scripts import v093_live_five_stage as live

class LiveStageTests(unittest.TestCase):
    def test_scope_and_routing(self):
        self.assertEqual((len(live.MONTHS),live.MONTHS[0],live.MONTHS[-1]),(322,'2026-10','2000-01'))
        for cat,owner in [('prices','PRICE'),('ex_dividend','PRICE'),('revenue_sii_0','FINANCIAL'),('IncomeStatement','FINANCIAL'),('institutional','CHIP'),('foreign_holdings','CHIP')]:
            self.assertEqual(live.route(cat),owner)
        with self.assertRaises(ValueError):live.route('unknown')
    def test_retry_only_transient(self):
        for status in (429,500,503):self.assertTrue(live.retryable(urllib.error.HTTPError('u',status,'err',{},None)))
        for status in (400,401,403,404):self.assertFalse(live.retryable(urllib.error.HTTPError('u',status,'err',{},None)))
        self.assertFalse(live.retryable(ValueError('schema')))
    def test_readback_hash_and_archive(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:z.writestr('unit.raw',b'native')
        receipt={'evidence_file':'file/unit.raw','sha256':live.native.sha(b'native')}
        with patch.object(live.native,'read',return_value=blob.getvalue()):
            self.assertEqual(live.payload(None,receipt),b'native')
            receipt['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):live.payload(None,receipt)
    def test_attempt_cap_survives_restart(self):
        w=object.__new__(live.Worker);job={'source':'TWSE','category':'prices','period':'2026-10-20'};key=live.engine.key(job)
        w.state={'units':{},'attempt_ledger':{'units':{key:4}}};w.circuit={}
        with patch.object(live.native,'request') as request:w.fetch_job(job,'units');request.assert_not_called()
    def test_permanent_errors_never_refetched(self):
        w=object.__new__(live.Worker);job={'source':'TWSE','category':'prices','period':'2026-10-20'};key=live.engine.key(job)
        w.state={'units':{key:{'permanent_hold':True}},'attempt_ledger':{}};w.circuit={}
        with patch.object(live.native,'request') as request:w.fetch_job(job,'units');request.assert_not_called()
    def test_crash_archive_recovery_requires_matching_identity(self):
        w=object.__new__(live.Worker);w.active='2026-10';w.state={'units':{},'stocks':[]}
        receipt={'run':live.RUN,'status':'SAVED_BASIC_VERIFIED','month':'2026-10','source':'TWSE','category':'prices','period':'2026-10-20','sha256':live.native.sha(b'raw')}
        w.inspect_payload('TWSE','unit.raw',b'raw',receipt,'archive/unit.raw')
        self.assertEqual(next(iter(w.state['units'].values()))['evidence_file'],'archive/unit.raw')
        with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):w.inspect_payload('TPEx','unit.raw',b'raw',receipt,'archive/unit.raw')
