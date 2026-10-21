import unittest
from unittest.mock import patch
from scripts.v093_isolated_full_file_metadata_gate import audit_year_range,summarize

class FullFileMetadataGateTests(unittest.TestCase):
    def test_duplicate_year_is_reported_without_reading_arbitrary_parent(self):
        def listing(d,parent):
            if parent=='ROOT':return [{'id':i,'name':'2000','mimeType':'application/vnd.google-apps.folder'} for i in ('A','B')]
            raise AssertionError('AMBIGUOUS_PARENT_READ')
        with patch('scripts.v093_isolated_full_file_metadata_gate.ROOT','ROOT'),patch('scripts.v093_isolated_full_file_metadata_gate.ls',side_effect=listing):
            r=audit_year_range(object(),2000,2000,'2000-01')
        self.assertEqual({x['status'] for x in r['months']['2000-01'].values()},{'DUPLICATE_YEAR_FOLDER'})
    def test_duplicate_source_is_reported_without_reading_arbitrary_parent(self):
        def listing(d,parent):
            if parent=='ROOT':return [{'id':'Y','name':'2000','mimeType':'application/vnd.google-apps.folder'}]
            if parent=='Y':return [{'id':i,'name':'TWSE','mimeType':'application/vnd.google-apps.folder'} for i in ('A','B')]
            raise AssertionError('AMBIGUOUS_PARENT_READ')
        with patch('scripts.v093_isolated_full_file_metadata_gate.ROOT','ROOT'),patch('scripts.v093_isolated_full_file_metadata_gate.ls',side_effect=listing):
            r=audit_year_range(object(),2000,2000,'2000-01')
        self.assertEqual(r['months']['2000-01']['TWSE']['status'],'DUPLICATE_SOURCE_FOLDER')
        self.assertEqual(r['months']['2000-01']['MOPS']['status'],'MISSING_SOURCE_FOLDER')
    def test_2000_january_empty_and_no_false_certification(self):
        def ls(d,parent):
            if parent=='ROOT':return [{'id':'Y','name':'2000','mimeType':'application/vnd.google-apps.folder'}]
            if parent=='Y':return [{'id':s,'name':s,'mimeType':'application/vnd.google-apps.folder'} for s in ('TWSE','TPEx','MOPS','FinMind')]
            if parent in ('TWSE','TPEx','MOPS','FinMind'):
                return [{'id':parent+'M','name':'2000-01','mimeType':'application/vnd.google-apps.folder'}]
            return []
        with patch('scripts.v093_isolated_full_file_metadata_gate.ROOT','ROOT'),patch('scripts.v093_isolated_full_file_metadata_gate.ls',side_effect=ls):
            r=audit_year_range(object(),2000,2000,'2000-01')
        self.assertEqual(len(r['months']),1)
        self.assertEqual(r['certified'],0)
        self.assertEqual({x['status'] for x in r['months']['2000-01'].values()},{'EMPTY_MONTH_FOLDER'})
    def test_duplicate_shard_rejected(self):
        with self.assertRaises(ValueError):
            summarize([{'months':{'2000-01':{}}},{'months':{'2000-01':{}}}])
    def test_invalid_year_rejected(self):
        with self.assertRaises(ValueError):audit_year_range(object(),1999,2026)
if __name__=='__main__':unittest.main()
