import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import v093_replanned_five_stage as worker_module
from scripts.v093_stage06_admission import analysis_gate, expected_unit_decision, read_repaired_staging
from scripts.v093_stage06_artifacts import LocalImmutableArtifacts
from scripts.v093_stage06_ledger import Ledger, FileStore, RULES, digest
from scripts.v093_stage06_native_repair import transform as native_transform
from scripts.v093_stage06_owner_replay import sha
from scripts.v093_stage06_raw_replay import RawReplayBinding, VERSION as RAW_VERSION
from scripts.v093_stage06_worker_bridge import RepairRuntime, run_pending_repairs
from tests import test_stage06_ledger as baseline


class NativeCounter:
    def __init__(self, used=0, saved=None):
        self.used, self.saved, self.hold = used, saved, False
        self.intents = []; self.finished = []
    def current(self, unit):
        return dict(used=self.used, saved_payload=self.saved,
                    evidence_sha256=digest(dict(unit=unit,used=self.used,saved=sha(self.saved) if self.saved else None)))
    def record_intent(self, unit, attempt, request_id):
        self.used=max(self.used,attempt);self.hold=True;self.intents.append(request_id)
    def finish(self, unit, response_sha, validation):
        self.finished.append(response_sha);self.hold=False


class RawRepairTests(unittest.TestCase):
    setUp=baseline.LedgerTests.setUp

    def prepare(self, prior=0, saved=None, source='TWSE', security='2330', evidence=None, supplement=None):
        self.unit.update(source=source,security_id=security)
        self.spec=dict(unit=copy.deepcopy(self.unit),job={'source':source,'url':{
            'TWSE':'https://www.twse.com.tw/test','TPEx':'https://www.tpex.org.tw/test',
            'MOPS':'https://mops.twse.com.tw/test','FinMind':'https://api.finmindtrade.com/api/v4/data'}[source]},
            evidence=evidence or dict(source_scope_verified=True,calendar_verified=True,universe_verified=True,
                availability_verified=True,applicable=True))
        if supplement is not None:self.spec['supplement']=supplement
        g=self.ledger.observe(self.unit,'RAW_MISSING','RAW',baseline.H,'RAW_TEST',prior_attempts=prior,
            attempt_evidence_sha256=baseline.PROOF,expected_evidence_sha256=digest(self.spec))
        self.ledger.approve_version('RAW',RAW_VERSION,baseline.PROOF)
        self.task=self.ledger.enqueue(g['gap_id'],baseline.H,RAW_VERSION,'RAW_TEST_RULES_V1')
        self.native=NativeCounter(prior,saved)
        self.payload=json.dumps(dict(source=source,date=self.unit['period_start'],stock_id=security,close='10.50')).encode()
        self.transport=Mock(return_value=self.payload)
        self.worker=SimpleNamespace(stage='RAW',owner='raw-owner',fence=1,lock='TEST_RAW')
        self.artifacts=LocalImmutableArtifacts(Path(self.tmp.name)/'artifacts')
        def validate(raw,unit):
            obj=json.loads(raw)
            if (obj['source'],obj['date'],obj['stock_id'])!=(unit['source'],unit['period_start'],unit['security_id']):
                raise ValueError('RAW_IDENTITY_DATE_MISMATCH')
            return dict(checks={k:True for k in RULES['RAW_MISSING'][1]},evidence={'native_cells':1,'numeric_semantics_verified':False})
        self.binding=RawReplayBinding(self.ledger,self.worker,self.artifacts,lambda unit:self.spec,self.transport,self.native,validate)
        return self.task

    def call(self):return self.binding(lambda:None,10)

    def test_intent_and_native_hold_are_durable_before_one_transport_call(self):
        self.prepare()
        def send(job):
            state=self.ledger.snapshot();a=next(iter(state['attempts'].values()))
            self.assertTrue(self.native.hold);self.assertEqual(self.native.used,1)
            self.assertEqual(next(iter(a['requests'].values()))['status'],'IN_FLIGHT')
            return self.payload
        self.transport.side_effect=send
        done=self.call();self.assertEqual(done['status'],'DONE');self.assertEqual(self.transport.call_count,1)
        self.assertFalse(self.native.hold)

    def test_fourth_attempt_is_last_without_reset(self):
        self.prepare(prior=3);self.assertEqual(self.call()['status'],'DONE')
        self.assertEqual(self.native.used,4)
        self.assertEqual(next(iter(self.ledger.snapshot()['attempts'].values()))['used'],4)

    def test_newer_native_counter_blocks_fifth_attempt(self):
        self.prepare(prior=3);self.native.used=4
        self.assertEqual(self.call()['status'],'RETRY_EXHAUSTED');self.transport.assert_not_called()

    def test_already_saved_fourth_response_is_reused_without_request(self):
        self.prepare(prior=4);self.native.saved=self.payload
        done=self.call();self.assertEqual(done['status'],'DONE');self.transport.assert_not_called()
        self.assertEqual(self.native.used,4)

    def test_unknown_transport_outcome_is_not_replayed_without_reconciliation(self):
        self.prepare();self.transport.side_effect=OSError('timeout')
        with self.assertRaises(OSError):self.call()
        self.now+=11;self.assertIsNone(self.call())
        self.assertEqual(self.transport.call_count,1);self.assertTrue(self.native.hold)
        request=next(iter(next(iter(self.ledger.snapshot()['attempts'].values()))['requests']))
        self.ledger.reconcile(self.task['task_id'],request,baseline.PROOF)
        self.transport.side_effect=None
        self.assertEqual(self.call()['status'],'DONE');self.assertEqual(self.native.used,2)

    def test_saved_response_after_crash_is_reconciled_and_not_downloaded_again(self):
        self.prepare()
        with patch.object(self.ledger,'end_request',side_effect=OSError('crash after save')):
            with self.assertRaises(OSError):self.call()
        self.now+=11;self.assertIsNone(self.call())
        request=next(iter(next(iter(self.ledger.snapshot()['attempts'].values()))['requests']))
        self.ledger.reconcile(self.task['task_id'],request,baseline.PROOF,sha(self.payload))
        self.assertEqual(self.call()['status'],'DONE');self.assertEqual(self.transport.call_count,1)

    def test_invalid_response_is_isolated_not_blindly_retried(self):
        self.prepare();self.transport.return_value=b'{"source":"TWSE","date":"1999-01-01","stock_id":"2330"}'
        with self.assertRaisesRegex(ValueError,'RAW_IDENTITY_DATE'):self.call()
        self.assertEqual(self.ledger.snapshot()['tasks'][self.task['task_id']]['status'],'FAILED_PERMANENT')
        self.assertIsNone(self.call());self.assertEqual(self.transport.call_count,1)

    def test_unverified_expected_scope_never_authorizes_download(self):
        self.prepare(evidence={'source_scope_verified':True})
        with self.assertRaisesRegex(ValueError,'EXPECTED_UNIT_NOT_PROVEN'):self.call()
        self.transport.assert_not_called()

    def test_future_scope_never_authorizes_download(self):
        self.unit.update(period_start='2026-10-30',period_end='2026-10-30');self.prepare()
        with self.assertRaisesRegex(ValueError,'FUTURE_UNIT'):self.call()
        self.transport.assert_not_called()

    def test_catalog_cannot_substitute_a_foreign_endpoint(self):
        self.prepare();self.spec['job']['url']='https://example.com/private'
        with self.assertRaisesRegex(ValueError,'CATALOG_EVIDENCE_MISMATCH'):self.call()
        self.transport.assert_not_called()

    def test_native_intent_persistence_failure_prevents_transport(self):
        self.prepare();self.native.record_intent=Mock(side_effect=OSError('native save failed'))
        with self.assertRaises(OSError):self.call()
        self.transport.assert_not_called()

    def test_finmind_requires_stock_gap_and_compatible_dimensions(self):
        proof=dict(official_gap_evidence_sha256=baseline.PROOF,official_gap_verified=True,definition_compatible=True,
            unit_compatible=True,sign_compatible=True,frequency_compatible=True,availability_compatible=True)
        self.prepare(source='FinMind',supplement=proof)
        self.assertEqual(self.call()['status'],'DONE');self.assertEqual(self.transport.call_count,1)

    def test_finmind_whole_market_scan_is_rejected(self):
        proof=dict(official_gap_evidence_sha256=baseline.PROOF,official_gap_verified=True,definition_compatible=True,
            unit_compatible=True,sign_compatible=True,frequency_compatible=True,availability_compatible=True)
        self.prepare(source='FinMind',security='ALL_MARKET',supplement=proof)
        with self.assertRaisesRegex(ValueError,'VERIFIED_STOCK_GAP_REQUIRED'):self.call()
        self.transport.assert_not_called()

    def test_raw_contract_cannot_bind_to_other_owner(self):
        self.prepare();self.worker.stage='PRICE'
        with self.assertRaisesRegex(ValueError,'RAW_OWNER_REQUIRED'):
            RawReplayBinding(self.ledger,self.worker,self.artifacts,None,None,None,None)


class WorkerBridgeTests(unittest.TestCase):
    setUp=baseline.LedgerTests.setUp
    def prepare(self,stage='PRICE',dataset='prices'):
        self.unit['dataset']=dataset
        owner=stage
        self.worker=SimpleNamespace(stage=owner,owner='worker-'+owner,fence=1,lock='POOL-'+owner,
            owned=Mock(),cursor={'month_index':7,'audit_month_index':2},until=time.monotonic()+100)
        raw=b'input';g=self.ledger.observe(self.unit,'BASIC_QA' if owner=='QA1' else 'PARSER_MAPPING',owner,sha(raw),'TEST')
        self.ledger.approve_version(owner,'BRIDGE_V1',baseline.PROOF)
        self.task=self.ledger.enqueue(g['gap_id'],sha(raw),'BRIDGE_V1','R1')
        checks=RULES['BASIC_QA' if owner=='QA1' else 'PARSER_MAPPING'][1]
        self.runtime=RepairRuntime(self.ledger,LocalImmutableArtifacts(Path(self.tmp.name)/'artifacts'),
            'BRIDGE_V1','R1',lambda unit:raw,lambda data,unit:data.upper(),
            lambda *args:dict(checks={k:True for k in checks},evidence={'test_only':True}),
            enabled=True,budget_seconds=10,max_tasks=1)
        return self.worker

    def test_disabled_hook_does_not_access_remote_or_primary_work(self):
        worker=SimpleNamespace()
        self.assertEqual(run_pending_repairs(worker)['status'],'DISABLED_NOT_CONFIGURED')

    def test_all_four_non_raw_owner_routes_preserve_cursor_and_hour_deadline(self):
        for stage,dataset in (('QA1','prices'),('PRICE','prices'),('FINANCIAL','revenue_twse'),('CHIP','institutional')):
            with self.subTest(stage=stage):
                worker=self.prepare(stage,dataset);before=copy.deepcopy(worker.cursor);until=worker.until
                result=run_pending_repairs(worker,self.runtime)
                self.assertEqual(len(result['completed_tasks']),1)
                self.assertEqual(worker.cursor,before);self.assertEqual(worker.until,until)

    def test_wrong_dataset_owner_does_not_recompute(self):
        worker=self.prepare('PRICE','institutional');self.runtime.transform=Mock()
        result=run_pending_repairs(worker,self.runtime)
        self.assertEqual(result['failed'],1);self.runtime.transform.assert_not_called()

    def test_budget_expiration_releases_task_for_later_work(self):
        worker=self.prepare();clock=[0]
        def slow(raw,unit):clock[0]=11;return raw
        self.runtime.transform=slow
        result=run_pending_repairs(worker,self.runtime,monotonic=lambda:clock[0])
        self.assertEqual(result['deferred'],1)
        self.assertEqual(self.ledger.snapshot()['tasks'][self.task['task_id']]['status'],'READY')

    def test_existing_quarantine_is_not_overwritten_by_new_repair(self):
        worker=self.prepare()
        key='unit_hash_'+worker_module.base.STAGING_REVISION
        legacy={'units':{key:{'status':'QUARANTINED'}},'corrections':{key:{'pending':True}}}
        before=copy.deepcopy(legacy)
        receipt={'category':'prices','unit_id':'unit','sha256':'hash'}
        with patch.object(worker_module,'newest_receipts',return_value=[receipt]),patch.object(worker_module,'cached_payload') as fetch:
            worker_module.Worker.process_units(worker,'2026-10',None,None,legacy,{})
        fetch.assert_not_called()
        result=run_pending_repairs(worker,self.runtime)
        self.assertEqual(len(result['completed_tasks']),1)
        self.assertTrue(result['completed_tasks'][0]['receipt']['output_key'].startswith('stage06/PRICE/'))
        self.assertEqual(legacy,before)

    def test_raw_persistence_or_transport_failure_stops_worker_before_primary_work(self):
        worker=self.prepare();worker.stage='RAW'
        self.runtime.raw_replay=Mock(side_effect=OSError('native persistence uncertain'))
        with self.assertRaises(OSError):run_pending_repairs(worker,self.runtime)
        self.runtime.raw_replay.assert_called_once()

    def test_primary_cursor_change_is_rejected(self):
        worker=self.prepare()
        def bad(raw,unit):worker.cursor['month_index']+=1;return raw
        self.runtime.transform=bad
        with self.assertRaisesRegex(ValueError,'PRIMARY_CURSOR'):run_pending_repairs(worker,self.runtime)

    def test_live_mode_cannot_be_accidentally_enabled(self):
        worker=self.prepare();self.runtime.test_only=False
        with self.assertRaisesRegex(ValueError,'NOT_ACTIVATED'):run_pending_repairs(worker,self.runtime)

    def test_real_worker_run_calls_repair_hook_and_still_runs_primary_work(self):
        context=self.prepare();w=object.__new__(worker_module.Worker);w.__dict__.update(context.__dict__)
        w.repair_runtime=self.runtime;w.consume=Mock();w.raw=Mock();w.putj=Mock()
        w.budget_seconds=3600;w.processed=0;w.saved=0;w.indexed=0;w.corrections=0
        w.last_processed_month=None;w.last_processed_period=None;w.primary_month=None
        w.stagectrl='TEST';w.api='TEST';w.token='TEST'
        with patch.object(worker_module,'commit'),patch.object(worker_module.base,'emit'):
            w.run()
        w.consume.assert_called_once();report=w.putj.call_args.args[2]
        self.assertEqual(report['stage06_completed_this_run'],1);self.assertEqual(report['worker_budget_minutes'],60)


class AdmissionTests(unittest.TestCase):
    def test_each_missing_analysis_requirement_blocks_approval(self):
        required=('schema_ok','source_identity_ok','numeric_semantics_ok','unit_ok','pit_ok','universe_ok','scope_complete','approved_processor')
        for key in required:
            evidence={k:True for k in required};evidence[key]=False
            with self.subTest(key=key):self.assertFalse(analysis_gate(evidence)['approved_for_analysis'])

    def test_unknown_expected_unit_does_not_create_download_work(self):
        self.assertEqual(expected_unit_decision({}),'IDENTITY_OR_EXPECTATION_HOLD')
        proof={k:True for k in ('source_scope_verified','calendar_verified','universe_verified','availability_verified')}
        self.assertEqual(expected_unit_decision(dict(proof,applicable=False)),'NOT_APPLICABLE')
        self.assertEqual(expected_unit_decision(dict(proof,applicable=True)),'EXPECTED')

    def test_native_index_and_event_contracts_are_separate_staging_streams(self):
        root=Path(__file__).parent/'fixtures/stage06_native';manifest=json.loads((root/'manifest.json').read_text())
        for entry in manifest:
            unit=entry['unit'];raw=(root/(unit['native_unit_id']+'.json')).read_bytes()
            result=read_repaired_staging(raw,native_transform(raw,unit),unit)
            stream='indices' if unit['dataset']=='indices' else 'securities'
            self.assertEqual(len(result['streams'][stream]),entry['expected_cells'])
            self.assertFalse(result['approved_for_analysis']);self.assertFalse(result['pit_verified'])


if __name__=='__main__':unittest.main()
