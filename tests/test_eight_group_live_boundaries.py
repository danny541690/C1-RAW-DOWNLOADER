import csv
import gzip
import tempfile
import unittest
from pathlib import Path
from scripts.v093_acceptance_integrated import recover_readback_scope, triage_content_failures, remote_metadata_observation
from scripts.v093_prelaunch_acceptance_batch import ArchiveCache, sha


class EightGroupLiveBoundaryTests(unittest.TestCase):
    def test_current_inventory_counts_do_not_approve_observation_universe(self):
        report=remote_metadata_observation(dict(schema='JARVIS_REMOTE_METADATA_V1',phase='DONE',enumeration_complete=True,
            observation_universe_approved=True,files=[{'id':'folder','mimeType':'application/vnd.google-apps.folder'},
                                                    {'id':'raw','mimeType':'application/json'}]))
        self.assertEqual(report['folders'],1);self.assertEqual(report['file_metadata_records'],1)
        self.assertTrue(report['root_enumeration_complete'])
        self.assertFalse(report['global_enumeration_complete']);self.assertFalse(report['observation_universe_approved'])
        self.assertFalse(report['raw_sha_readback_verified'])

    def test_invalid_inventory_or_string_complete_flag_does_not_pass(self):
        report=remote_metadata_observation(dict(schema='JARVIS_REMOTE_METADATA_V1',phase='DONE',enumeration_complete='true',files=[]))
        self.assertFalse(report['root_enumeration_complete'])
        for files in ({},[{'id':'raw'}],[{'id':'same','mimeType':'text/plain'}]*2):
            with self.assertRaises(ValueError):remote_metadata_observation(dict(schema='JARVIS_REMOTE_METADATA_V1',files=files))

    def test_zero_restorable_packages_cannot_pass_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            result=recover_readback_scope({'archive_readbacks':{}},[],p,p,ArchiveCache())
            self.assertEqual(result['result'],'NOT_EXECUTED_NO_READBACK_SCOPE')
            self.assertEqual(result['units_verified'],0)
            self.assertFalse(result['full_database_restore_verified'])

    def test_empty_income_and_cashflow_bodies_require_source_review(self):
        for dataset in ('IncomeStatement','CashflowStatement'):
            with self.subTest(dataset=dataset), tempfile.TemporaryDirectory() as directory:
                p=Path(directory);cache=p/'cache';cache.mkdir();content=p/'content';content.mkdir()
                raw=b'<table id="bodyTable"><tbody></tbody></table><input name="yearseason" value="2005Q3">'
                (cache/'file1').write_bytes(raw)
                row=dict(task_key='MOPS|unit1',source='MOPS',dataset=dataset,period='2005-09-30',
                         raw_reference='file1',raw_sha256=sha(raw),status='CONTENT_BLOCKED',next_action='ACCOUNT_MATRIX_ROW_MISMATCH')
                with gzip.open(content/'next_round.csv.gz','wt',encoding='utf-8-sig',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=row);writer.writeheader();writer.writerow(row)
                result=triage_content_failures(content,cache,ArchiveCache())[0]
                self.assertEqual(result['proposed_queue'],'SOURCE_ROUTE_REVIEW')
                self.assertEqual(result['diagnosis'],'RETAINED_MOPS_RESPONSE_HAS_NO_ACCOUNT_ROWS')
                self.assertFalse(result['raw_changed'])


if __name__=='__main__':unittest.main()
