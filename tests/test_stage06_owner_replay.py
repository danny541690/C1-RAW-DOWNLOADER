import copy
import json
import unittest
from pathlib import Path
from scripts import v093_stage06_ledger as m
from scripts import v093_stage06_owner_replay as replay
from tests import test_stage06_ledger as baseline
H, OUT, PROOF = baseline.H, baseline.OUT, baseline.PROOF

class Artifacts:
    def __init__(self):
        self.data={};self.corrupt_output=False;self.corrupt_proof=False;self.crash=False
    def put_immutable(self,key,raw,guard):
        guard()
        if key in self.data and self.data[key]!=raw:raise ValueError('IMMUTABLE_ARTIFACT_CONFLICT')
        self.data.setdefault(key,raw)
        if self.crash:
            self.crash=False
            raise OSError('crash after durable output')
    def read(self,key):
        raw=self.data[key]
        if self.corrupt_output and key.endswith('/output'):return b'corrupted'
        if self.corrupt_proof and '/validation-' in key:return b'corrupted'
        return raw

class OwnerReplayTests(unittest.TestCase):
    setUp=baseline.LedgerTests.setUp
    gap=baseline.LedgerTests.gap
    task=baseline.LedgerTests.task
    claim=baseline.LedgerTests.claim
    receipt=baseline.LedgerTests.receipt

    def prepare(self,owner='PRICE',kind='PARSER_MAPPING',version='V1',rules='RULES_V1'):
        evidence=replay.sha(b'input')
        g=self.ledger.observe(self.unit,kind,owner,evidence,'TEST_GAP')
        self.ledger.approve_version(owner,version,PROOF)
        return self.ledger.enqueue(g['gap_id'],evidence,version,rules)

    def run_replay(self,artifacts=None,owner='PRICE',validator=None,transform=None,read=None,lease=None):
        self.artifacts=artifacts or getattr(self,'artifacts',Artifacts())
        def validate(raw,saved,unit):
            return {'checks':{k:True for k in m.RULES['BASIC_QA' if owner=='QA1' else 'PARSER_MAPPING'][1]},
                    'evidence':{'input_length':len(raw),'output_length':len(saved),'test_only':True}}
        return replay.replay_one(self.ledger,owner,'replay-worker','V1','RULES_V1',
            read or (lambda unit:b'input'),transform or (lambda raw,unit:raw.upper()),
            validator or validate,self.artifacts,lease or (lambda:None),ttl=10)

    def assert_open(self,task):
        self.assertNotEqual(self.ledger.snapshot()['gaps'][task['gap_id']]['status'],'RESOLVED')

    def test_each_non_raw_owner_completes_only_with_readback_evidence(self):
        for owner in ('QA1','PRICE','FINANCIAL','CHIP'):
            with self.subTest(owner=owner):
                self.unit['native_unit_id']=owner
                t=self.prepare(owner,'BASIC_QA' if owner=='QA1' else 'PARSER_MAPPING')
                done=self.run_replay(owner=owner)
                self.assertEqual(done['status'],'DONE')
                self.assertEqual(done['receipt']['rule_version'],'RULES_V1')
                proof=self.artifacts.read(done['receipt']['validation_key'])
                self.assertEqual(replay.sha(proof),done['receipt']['validation_evidence_sha256'])
                self.assertFalse(m.summary(self.ledger.snapshot())['numeric_verified'])

    def test_wrong_input_hash_never_writes_output(self):
        t=self.prepare()
        with self.assertRaisesRegex(ValueError,'INPUT_READBACK_HASH'):
            self.run_replay(read=lambda unit:b'wrong')
        self.assertEqual(self.artifacts.data,{})
        self.assert_open(t)

    def test_corrupt_output_readback_keeps_gap_open(self):
        t=self.prepare();a=Artifacts();a.corrupt_output=True
        with self.assertRaisesRegex(ValueError,'OUTPUT_READBACK_HASH'):
            self.run_replay(a)
        self.assert_open(t)

    def test_corrupt_validation_readback_keeps_gap_open(self):
        t=self.prepare();a=Artifacts();a.corrupt_proof=True
        with self.assertRaisesRegex(ValueError,'VALIDATION_READBACK_HASH'):
            self.run_replay(a)
        self.assert_open(t)

    def test_empty_validation_evidence_cannot_close(self):
        t=self.prepare()
        with self.assertRaisesRegex(ValueError,'VALIDATOR_EVIDENCE_REQUIRED'):
            self.run_replay(validator=lambda *args:{'checks':{},'evidence':{}})
        self.assert_open(t)

    def test_false_validator_check_cannot_close(self):
        t=self.prepare()
        with self.assertRaisesRegex(ValueError,'GAP_SPECIFIC'):
            self.run_replay(validator=lambda *args:{'checks':{'parser_ok':False},'evidence':{'reason':'failed'}})
        self.assert_open(t)

    def test_lease_expires_during_transform_prevents_artifact_write(self):
        t=self.prepare()
        def slow(raw,unit):
            self.now+=11
            return b'output'
        with self.assertRaises(m.StaleClaim):
            self.run_replay(transform=slow)
        self.assertEqual(self.artifacts.data,{})
        self.assert_open(t)

    def test_owner_lease_loss_prevents_claim(self):
        self.prepare()
        def lost():raise m.StaleClaim('live owner expired')
        with self.assertRaises(m.StaleClaim):self.run_replay(lease=lost)
        self.assertEqual(next(iter(self.ledger.snapshot()['tasks'].values()))['status'],'READY')

    def test_crash_after_output_reuses_immutable_output_then_completes(self):
        t=self.prepare();a=Artifacts();a.crash=True
        with self.assertRaises(OSError):self.run_replay(a)
        self.assertEqual(len(a.data),1)
        self.now+=11
        done=self.run_replay(a)
        self.assertEqual(done['status'],'DONE')
        self.assertEqual(done['fence'],2)
        self.assertEqual(len(a.data),2)

    def test_different_output_after_crash_cannot_overwrite_artifact(self):
        t=self.prepare();a=Artifacts();a.crash=True
        with self.assertRaises(OSError):self.run_replay(a)
        self.now+=11
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_ARTIFACT_CONFLICT'):
            self.run_replay(a,transform=lambda raw,unit:b'different')
        self.assertEqual(next(iter(a.data.values())),b'INPUT')
        self.assert_open(t)

    def test_processor_filter_leaves_other_version_for_correct_worker(self):
        self.prepare(version='OTHER')
        self.assertIsNone(self.run_replay())
        self.assertEqual(next(iter(self.ledger.snapshot()['tasks'].values()))['status'],'READY')

    def test_rule_filter_leaves_other_rules_unclaimed(self):
        self.prepare(rules='OTHER_RULES')
        self.assertIsNone(self.run_replay())

    def test_numeric_gap_is_not_closed_by_parser_adapter(self):
        self.prepare(kind='NUMERIC_CONFLICT')
        self.assertIsNone(self.run_replay())

    def test_raw_adapter_refuses_download_work(self):
        with self.assertRaisesRegex(ValueError,'RAW_REQUIRES_DURABLE_HTTP_ADAPTER'):
            self.run_replay(owner='RAW')

class IdentityReconciliationTests(unittest.TestCase):
    setUp=baseline.LedgerTests.setUp
    def fixture(self):
        return json.loads((Path(__file__).parent/'fixtures/stage06_legacy_identity_202610.json').read_text())
    def hold(self,row):
        m.import_quarantine(self.ledger,'PRICE',{'month':'2026-10','units':{'legacy':row}})
        return next(iter(self.ledger.snapshot()['import_holds']))
    def test_three_real_legacy_receipts_join_unique_native_hash_and_period(self):
        f=self.fixture()
        for row in f['receipts']:
            hid=self.hold(row) if not self.ledger.snapshot()['import_holds'] else None
            if hid is None:
                m.import_quarantine(self.ledger,'PRICE',{'month':'2026-10','units':{row['unit_id']:row}})
                hid=next(k for k,h in self.ledger.snapshot()['import_holds'].items() if h['unit_id']==row['unit_id'])
            gap=self.ledger.reconcile_identity(hid,row,f['registry'],m.digest(f['registry']))
            task=self.ledger.enqueue(gap['gap_id'],row['raw_sha256'],'CANDIDATE_MAPPING_FIX_V1','STAGE06_RULES_V1')
            self.assertEqual(task['status'],'BLOCKED_APPROVAL')
        result=m.summary(self.ledger.snapshot())
        self.assertEqual((result['gaps'],result['tasks'],result['identity_holds'],result['identities_reconciled']),(3,3,0,3))
        self.assertEqual({g['unit']['dataset'] for g in self.ledger.snapshot()['gaps'].values()},{'indices','capital_reduction'})

    def test_original_receipt_cannot_be_changed(self):
        f=self.fixture();row=f['receipts'][0];hid=self.hold(row)
        altered=dict(row,raw_sha256=OUT)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_RECEIPT_EVIDENCE'):
            self.ledger.reconcile_identity(hid,altered,f['registry'],PROOF)

    def test_different_native_hash_cannot_resolve_identity(self):
        f=self.fixture();row=f['receipts'][0];hid=self.hold(row)
        registry=copy.deepcopy(f['registry'])
        for r in registry:r['sha256']=OUT
        with self.assertRaisesRegex(ValueError,'NATIVE_RECEIPT_NOT_UNIQUE'):
            self.ledger.reconcile_identity(hid,row,registry,PROOF)

    def test_ambiguous_native_identity_is_held(self):
        f=self.fixture();row=f['receipts'][0];hid=self.hold(row)
        candidate=next(r for r in f['registry'] if r['unit_id']==row['unit_id'])
        registry=f['registry']+[dict(candidate,period='2026-09')]
        with self.assertRaisesRegex(ValueError,'NATIVE_RECEIPT_NOT_UNIQUE'):
            self.ledger.reconcile_identity(hid,row,registry,PROOF)
        self.assertEqual(m.summary(self.ledger.snapshot())['identity_holds'],1)
        self.assertEqual(len(self.ledger.snapshot()['gaps']),0)

    def test_repeat_reconciliation_is_idempotent_and_does_not_approve_data(self):
        f=self.fixture();row=f['receipts'][0];hid=self.hold(row)
        self.ledger.reconcile_identity(hid,row,f['registry'],PROOF)
        before=self.path.read_bytes()
        self.ledger.reconcile_identity(hid,row,f['registry'],PROOF)
        self.assertEqual(self.path.read_bytes(),before)
        result=m.summary(self.ledger.snapshot())
        self.assertFalse(result['numeric_verified']);self.assertFalse(result['pit_verified'])

if __name__=='__main__':unittest.main()
