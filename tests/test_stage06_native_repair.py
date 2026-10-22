import concurrent.futures
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from scripts import v093_stage06_native_repair as n
from scripts.v093_stage06_artifacts import LocalImmutableArtifacts
from scripts.v093_stage06_ledger import Ledger, FileStore, StaleClaim, digest
from scripts.v093_stage06_owner_replay import replay_one

FIXTURES = Path(__file__).parent / 'fixtures/stage06_native'


class NativeRepairTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        self.entry = next(x for x in self.manifest if x['unit']['period_start'] == '2026-10-20')
        self.unit = self.entry['unit']
        self.raw = (FIXTURES / (self.unit['native_unit_id'] + '.json')).read_bytes()

    def changed(self, fn):
        obj = json.loads(self.raw); fn(obj)
        return json.dumps(obj, ensure_ascii=False).encode()

    def changed_output(self, fn, meta_fn=None):
        table = pq.read_table(io.BytesIO(n.transform(self.raw, self.unit)))
        rows = table.to_pylist(); fn(rows)
        metadata = dict(table.schema.metadata)
        if meta_fn:
            meta = json.loads(metadata[b'jarvis_stage06']); meta_fn(meta)
            metadata[b'jarvis_stage06'] = json.dumps(meta).encode()
        table = pa.Table.from_pylist(rows, schema=n.SCHEMA).replace_schema_metadata(metadata)
        buf = io.BytesIO(); pq.write_table(table, buf)
        return buf.getvalue()

    def test_four_real_payloads_match_pinned_hashes_records_and_cells(self):
        for x in self.manifest:
            with self.subTest(unit=x['unit']['native_unit_id']):
                raw = (FIXTURES / (x['unit']['native_unit_id'] + '.json')).read_bytes()
                self.assertEqual(n.sha(raw), x['input_sha256'])
                proof = n.validate_output(raw, n.transform(raw, x['unit']), x['unit'])['evidence']
                self.assertEqual(proof['cells_compared'], x['expected_cells'])
                self.assertEqual(proof['native_records'], x['expected_records'])

    def test_price_and_total_return_series_are_distinct_without_fake_stock_code(self):
        rows = pq.read_table(io.BytesIO(n.transform(self.raw, self.unit))).to_pylist()
        selected = [r for r in rows if r['native_name'] == '櫃買指數' and r['native_field'] == '收市指數']
        self.assertEqual({r['series_kind'] for r in selected}, {'PRICE_INDEX', 'TOTAL_RETURN_INDEX'})
        self.assertEqual({r['decimal_text'] for r in selected}, {'387.88', '721.44'})
        self.assertTrue(all(r['security_id'] is None and r['entity_type'] == 'INDEX' for r in rows))

    def test_event_uses_native_resumption_date_not_query_month(self):
        x = next(x for x in self.manifest if x['unit']['dataset'] == 'capital_reduction')
        raw = (FIXTURES / (x['unit']['native_unit_id'] + '.json')).read_bytes()
        rows = pq.read_table(io.BytesIO(n.transform(raw, x['unit']))).to_pylist()
        self.assertEqual({(r['security_id'], r['date']) for r in rows}, {('2601', '2026-10-05'), ('2323', '2026-10-12')})
        self.assertTrue(all(r['date_role'] == 'RESUMPTION_DATE' for r in rows))

    def test_ex_dividend_preserves_native_precision_and_fund_code(self):
        x = next(x for x in self.manifest if x['unit']['dataset'] == 'ex_dividend')
        raw = (FIXTURES / (x['unit']['native_unit_id'] + '.json')).read_bytes()
        rows = pq.read_table(io.BytesIO(n.transform(raw, x['unit']))).to_pylist()
        self.assertIn('00950B', {r['security_id'] for r in rows})
        self.assertIn('0.61725044', {r['decimal_text'] for r in rows})

    def test_wrong_market_or_security_scope_is_rejected(self):
        for override in ({'market': 'TSE'}, {'security_id': '2330'}):
            with self.subTest(override=override), self.assertRaisesRegex(ValueError, 'SCOPE_MISMATCH'):
                n.transform(self.raw, dict(self.unit, **override))

    def test_width_mismatch_is_not_silently_skipped(self):
        raw = self.changed(lambda o: o['tables'][0]['data'][0].pop())
        with self.assertRaisesRegex(ValueError, 'ROW_WIDTH'): n.transform(raw, self.unit)

    def test_missing_index_schema_is_rejected(self):
        raw = self.changed(lambda o: o['tables'][0]['fields'].__setitem__(1, 'unknown'))
        with self.assertRaisesRegex(ValueError, 'INDEX_SCHEMA'): n.transform(raw, self.unit)

    def test_table_and_response_date_conflict_is_rejected(self):
        raw = self.changed(lambda o: o['tables'][0].__setitem__('date', '115/10/19'))
        with self.assertRaisesRegex(ValueError, 'DATE_CONFLICT'): n.transform(raw, self.unit)

    def test_wrong_task_date_is_rejected(self):
        unit = dict(self.unit, period_start='2026-10-19', period_end='2026-10-19')
        with self.assertRaisesRegex(ValueError, 'DATE_OUTSIDE_TASK_SCOPE'): n.transform(self.raw, unit)

    def test_invalid_numeric_cell_is_not_silently_dropped(self):
        raw = self.changed(lambda o: o['tables'][0]['data'][0].__setitem__(1, 'bad'))
        with self.assertRaisesRegex(ValueError, 'INVALID_NUMERIC'): n.transform(raw, self.unit)

    def test_missing_number_is_preserved_as_missing_not_zero(self):
        raw = self.changed(lambda o: o['tables'][0]['data'][0].__setitem__(1, '--'))
        proof = n.validate_output(raw, n.transform(raw, self.unit), self.unit)
        self.assertEqual(proof['evidence']['cells_compared'], self.entry['expected_cells'] - 1)

    def test_duplicate_header_is_rejected(self):
        raw = self.changed(lambda o: o['tables'][0]['fields'].__setitem__(1, '指數'))
        with self.assertRaisesRegex(ValueError, 'INVALID_NATIVE_TABLE'): n.transform(raw, self.unit)

    def test_event_security_identity_is_required(self):
        x = next(x for x in self.manifest if x['unit']['dataset'] == 'capital_reduction')
        obj = json.loads((FIXTURES / (x['unit']['native_unit_id'] + '.json')).read_bytes())
        obj['data'][0][1] = ''
        with self.assertRaisesRegex(ValueError, 'SECURITY_ID'):
            n.transform(json.dumps(obj).encode(), x['unit'])

    def test_source_error_response_cannot_be_repaired_as_data(self):
        raw = self.changed(lambda o: o.__setitem__('stat', 'error'))
        with self.assertRaisesRegex(ValueError, 'UNSUCCESSFUL_SOURCE'): n.transform(raw, self.unit)

    def test_stored_numeric_mutation_is_detected_independently(self):
        output = self.changed_output(lambda rows: rows[0].__setitem__('decimal_text', '123'))
        with self.assertRaisesRegex(ValueError, 'NUMERIC_CELL'): n.validate_output(self.raw, output, self.unit)

    def test_missing_stored_cell_is_detected(self):
        output = self.changed_output(lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, 'MISSING_OUTPUT_CELLS'): n.validate_output(self.raw, output, self.unit)

    def test_stored_identity_mutation_is_detected(self):
        output = self.changed_output(lambda rows: rows[0].__setitem__('security_id', '2330'))
        with self.assertRaisesRegex(ValueError, 'INDEX_IDENTITY'): n.validate_output(self.raw, output, self.unit)

    def test_fabricated_approval_flag_is_rejected(self):
        output = self.changed_output(lambda rows: None, lambda meta: meta.__setitem__('pit_verified', True))
        with self.assertRaisesRegex(ValueError, 'APPROVAL_CLAIM'): n.validate_output(self.raw, output, self.unit)

    def test_different_raw_cannot_use_previous_output_provenance(self):
        output = n.transform(self.raw, self.unit)
        with self.assertRaisesRegex(ValueError, 'PROVENANCE_MISMATCH'):
            n.validate_output(self.raw + b' ', output, self.unit)

    def test_real_file_backend_replays_all_four_fixtures_with_validated_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(FileStore(Path(root) / 'ledger.json'))
            artifacts = LocalImmutableArtifacts(Path(root) / 'artifacts')
            ledger.approve_version('PRICE', n.VERSION, digest('TEST_ONLY_REGRESSION_EVIDENCE'))
            for x in self.manifest:
                raw = (FIXTURES / (x['unit']['native_unit_id'] + '.json')).read_bytes()
                gap = ledger.observe(x['unit'], 'PARSER_MAPPING', 'PRICE', n.sha(raw), 'PARSER_TEST')
                ledger.enqueue(gap['gap_id'], n.sha(raw), n.VERSION, 'TEST_RULES_V1')
                done = replay_one(ledger, 'PRICE', 'test-owner', n.VERSION, 'TEST_RULES_V1',
                    lambda unit: raw, n.transform, n.validate_output, artifacts, lambda: None)
                self.assertEqual(done['status'], 'DONE')
                receipt = done['receipt']
                proof = json.loads(artifacts.read(receipt['validation_key']))
                self.assertEqual(proof['validation']['evidence']['cells_compared'], x['expected_cells'])
                self.assertFalse(proof['validation']['evidence']['numeric_semantics_verified'])


class ImmutableArtifactTests(unittest.TestCase):
    def test_expired_guard_cannot_publish(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalImmutableArtifacts(root)
            def expired(): raise StaleClaim('expired')
            with self.assertRaises(StaleClaim): store.put_immutable('key', b'one', expired)
            self.assertFalse(store.path('key').exists())

    def test_existing_bytes_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalImmutableArtifacts(root)
            store.put_immutable('key', b'one', lambda: None)
            store.put_immutable('key', b'one', lambda: None)
            with self.assertRaisesRegex(ValueError, 'IMMUTABLE'): store.put_immutable('key', b'two', lambda: None)
            self.assertEqual(store.read('key'), b'one')

    def test_two_backends_publish_only_one_value_for_same_key(self):
        with tempfile.TemporaryDirectory() as root:
            def put(value):
                try:
                    LocalImmutableArtifacts(root).put_immutable('key', value, lambda: None)
                    return True
                except ValueError:
                    return False
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                result = list(pool.map(put, (b'one', b'two')))
            self.assertEqual(sum(result), 1)


if __name__ == '__main__': unittest.main()
