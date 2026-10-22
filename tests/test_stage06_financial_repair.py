import copy
import io
import json
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from scripts import v093_stage06_financial_repair as f
from scripts.v093_stage06_coverage import reconcile_raw_snapshot, coverage_snapshot, completion_gate
from scripts.v093_stage06_ledger import empty, digest
from scripts import v093_stage06_live as live


def sample(report='CashflowStatement'):
    labels={'CashflowStatement':['營業活動之淨現金流入（流出）','期末現金及約當現金餘額'],
        'BalanceSheet':['資產總計','負債總計'], 'IncomeStatement':['營業收入合計','本期淨利（淨損）']}[report]
    left=''.join('<tr><td>'+x+'</td></tr>' for x in labels)
    return ('''<div>金額單位：新台幣仟元</div>
    <input name="yearseason" value="2023Q1"><input name="year" value="2023"><input name="season" value="1">
    <input name="reportName" value="2330 台積電"><input name="reportName" value="2317 鴻海">
    <div id="headTable"><table><tbody>'''+left+'''</tbody></table></div>
    <div id="bodyTable"><table><thead><tr><td>合併</td><td>個別</td></tr><tr><td>2330 台積電</td><td>2317 鴻海</td></tr></thead>
    <tbody><tr><td>1,234.50</td><td>-20</td></tr><tr><td>--</td><td>(30)</td></tr></tbody></table></div>''').encode()


class FinancialMatrixTests(unittest.TestCase):
    def setUp(self):
        self.unit=dict(source='MOPS',market='UNKNOWN',dataset='CashflowStatement',security_id='ALL_MARKET',
            period_start='2023-03-31',period_end='2023-03-31',native_unit_id='matrix-unit')
        self.raw=sample()

    def encode(self,rows):
        buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows,schema=f.SCHEMA),buf);return buf.getvalue()

    def rows(self):return pq.read_table(io.BytesIO(f.transform(self.raw,self.unit))).to_pylist()

    def test_three_statement_formats_preserve_period_kind(self):
        for kind in f.REPORTS:
            u=dict(self.unit,dataset=kind);raw=sample(kind);out=f.transform(raw,u)
            evidence=f.validate_output(raw,out,u)['evidence']
            self.assertEqual(evidence['cells_compared'],3)
            self.assertEqual(evidence['period_kind'],'INSTANT' if kind=='BalanceSheet' else 'YTD')

    def test_blank_is_not_zero_and_sign_and_decimal_are_preserved(self):
        rows=self.rows();self.assertEqual([r['decimal_text'] for r in rows],['1234.50','-20','-30'])
        self.assertEqual(len(rows),3);self.assertEqual(rows[0]['security_id'],'2330')

    def test_unit_scope_and_unannounced_period_not_inferred(self):
        rows=self.rows();self.assertEqual(rows[0]['native_unit_text'],'新台幣仟元')
        self.assertEqual(rows[0]['statement_scope'],'合併');self.assertEqual(rows[1]['statement_scope'],'個別')
        self.assertTrue(all(r['announcement_time'] is None for r in rows))

    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):f.transform(self.raw,dict(self.unit,source='FinMind'))

    def test_period_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError,'PERIOD_CONFLICT'):f.transform(self.raw.replace(b'2023Q1',b'2023Q2'),self.unit)

    def test_duplicate_periods_rejected(self):
        with self.assertRaisesRegex(ValueError,'PERIOD'):f.transform(self.raw+b'<input name="yearseason" value="2022Q1">',self.unit)

    def test_wrong_statement_type_rejected(self):
        with self.assertRaisesRegex(ValueError,'TYPE_UNPROVEN'):f.transform(self.raw,dict(self.unit,dataset='BalanceSheet'))

    def test_reordered_company_columns_rejected(self):
        raw=self.raw.decode().replace('<td>2330 台積電</td><td>2317 鴻海</td>','<td>2317 鴻海</td><td>2330 台積電</td>').encode()
        with self.assertRaisesRegex(ValueError,'COLUMN_ORDER'):f.transform(raw,self.unit)

    def test_missing_account_row_rejected(self):
        raw=self.raw.decode().replace('<tr><td>期末現金及約當現金餘額</td></tr>','').encode()
        with self.assertRaisesRegex(ValueError,'ROW_MISMATCH'):f.transform(raw,self.unit)

    def test_missing_company_cell_rejected(self):
        with self.assertRaisesRegex(ValueError,'WIDTH_MISMATCH'):f.transform(self.raw.replace(b'<td>-20</td>',b''),self.unit)

    def test_unproven_spans_rejected(self):
        with self.assertRaisesRegex(ValueError,'SPAN'):f.transform(self.raw.replace(b'<td>-20',b'<td colspan="2">-20'),self.unit)

    def test_unknown_value_not_silently_discarded(self):
        with self.assertRaisesRegex(ValueError,'UNRECOGNIZED'):f.transform(self.raw.replace(b'-20',b'unsupported'),self.unit)

    def test_missing_unit_rejected(self):
        raw=self.raw.decode().replace('金額單位：新台幣仟元','無單位').encode()
        with self.assertRaisesRegex(ValueError,'UNIT_UNPROVEN'):f.transform(raw,self.unit)

    def test_validator_rejects_dropped_cell(self):
        with self.assertRaisesRegex(ValueError,'MISSING_OR_EXTRA'):f.validate_output(self.raw,self.encode(self.rows()[:-1]),self.unit)

    def test_validator_rejects_numeric_change(self):
        rows=self.rows();rows[0]['decimal_text']='12345'
        with self.assertRaisesRegex(ValueError,'NUMERIC_CELL'):f.validate_output(self.raw,self.encode(rows),self.unit)

    def test_validator_rejects_wrong_company_and_quarterly_conversion(self):
        for key,value in (('security_id','2454'),('period_kind','QUARTERLY'),('statement_scope','個別'),('announcement_time','2023-03-31')):
            rows=self.rows();rows[0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'CONTEXT_MISMATCH'):
                f.validate_output(self.raw,self.encode(rows),self.unit)

    def test_blocked_financial_task_is_upgraded_without_changing_old_receipt(self):
        row=dict(status='QUARANTINED',source='MOPS',category='BalanceSheet',period='2023-03-31',
            unit_id='financial-old',raw_sha256=digest('raw'),error='NO_PARSED_NUMERIC_CELLS')
        state={'month':'2023-03','units':{'old':row}};before=copy.deepcopy(state)
        from scripts.v093_stage06_ledger import Ledger,FileStore,import_quarantine
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Ledger(FileStore(Path(tmp)/'ledger.json'))
            import_quarantine(ledger,'FINANCIAL',state,'UNAPPROVED_FINANCIAL_REPAIR_V1',live.RULE_VERSION)
            prior=ledger.snapshot()
        out=live.reconcile_snapshot(prior,'FINANCIAL',state,[])
        self.assertEqual(state,before)
        self.assertEqual([t['status'] for t in out['tasks'].values()].count('READY'),1)
        self.assertIn('FINANCIAL:'+f.VERSION,out['approved_versions'])

    def test_financial_staging_consumer_does_not_approve_analysis(self):
        from scripts.v093_stage06_admission import read_repaired_staging
        out=f.transform(self.raw,self.unit);r=read_repaired_staging(self.raw,out,self.unit)
        self.assertEqual(len(r['streams']['financial_statements']),3)
        self.assertFalse(r['approved_for_analysis']);self.assertFalse(r['pit_verified'])

    def test_real_income_trial_activates_statement_adapter(self):
        self.assertEqual(live.supported_version('FINANCIAL',dict(self.unit,dataset='IncomeStatement')),f.VERSION)


class AllDataCoverageTests(unittest.TestCase):
    def raw(self):return dict(source='TWSE',category='prices',period='2026-10-01',unit_id='raw-missing',status='ISOLATED_MISSING',attempts=4)

    def test_raw_failure_is_recorded_without_new_network_attempt(self):
        row=self.raw();state={'units':{'raw-missing':row},'attempt_ledger':{'units':{'raw-missing':4}}}
        out=reconcile_raw_snapshot(empty(),[state]);self.assertFalse(out['tasks'])
        self.assertEqual(next(iter(out['attempts'].values()))['used'],4)
        self.assertEqual(next(iter(out['gaps'].values()))['owner'],'RAW')

    def test_raw_reconciliation_does_not_reset_existing_counters(self):
        row=self.raw();out=reconcile_raw_snapshot(empty(),[{'units':{'x':row}}]);row['attempts']=1
        again=reconcile_raw_snapshot(out,[{'units':{'x':row}}])
        self.assertEqual(next(iter(again['attempts'].values()))['used'],4)

    def test_verified_raw_not_marked_missing(self):
        row=dict(self.raw(),status='SAVED_BASIC_VERIFIED')
        self.assertFalse(reconcile_raw_snapshot(empty(),[{'units':{'x':row}}])['gaps'])

    def test_bad_identity_is_visible_instead_of_dropped(self):
        out=reconcile_raw_snapshot(empty(),[{'units':{'x':{'status':'FAILED'}}}])
        self.assertEqual(len(out['import_holds']),1)

    def test_empty_month_or_missing_source_is_not_complete(self):
        c=coverage_snapshot([]);self.assertFalse(c['coverage_certified'])
        self.assertEqual(c['source_receipt_counts'],dict.fromkeys(('TWSE','TPEx','MOPS','FinMind'),0))

    def test_scan_done_and_zero_known_gaps_are_insufficient(self):
        r=completion_gate({'scan_complete':True,'unresolved_count':0})
        self.assertFalse(r['complete']);self.assertIn('expected_catalog_complete',r['blocked_by'])

    def test_each_missing_completion_dimension_blocks_final_completion(self):
        keys=('expected_catalog_complete','all_required_sources_checked','all_expected_units_present','all_raw_hashes_verified',
            'all_financial_accounts_verified','all_repairs_validated','unit_semantics_verified','historical_universe_verified','pit_verified')
        evidence=dict.fromkeys(keys,True);evidence['unresolved_count']=0
        self.assertTrue(completion_gate(evidence)['complete'])
        for key in keys:
            with self.subTest(key=key):self.assertFalse(completion_gate(dict(evidence,**{key:False}))['complete'])

    def test_registry_includes_all_financial_statements_and_extra_source_candidates(self):
        r=json.loads(Path('config/v093_stage06_dataset_registry.json').read_text())
        financial=next(x for x in r['families'] if x['id']=='FINANCIAL_STATEMENTS')
        self.assertEqual(set(financial['datasets']),set(f.REPORTS))
        extra={x['source']:x for x in r['source_registry']}
        for source in ('Goodinfo','FinLab','TDCC','Fugle'):self.assertFalse(extra[source]['automatic_download_enabled'])


if __name__=='__main__':unittest.main()
