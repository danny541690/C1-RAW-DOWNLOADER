import unittest
from unittest.mock import patch
from scripts.v093_isolated_duplicate_boundary_audit import audit_year,FOLDER
class DuplicateBoundaryTests(unittest.TestCase):
    def test_same_name_different_hash_quarantined(self):
        class Api:
            def files(self):return self
            def get_media(self,fileId):return fileId.encode()
        class Drive:
            api=Api()
            def call(self,fn):return fn()
        def ls(d,p):
            if p=='ROOT':return [{'id':'Y','name':'2019','mimeType':FOLDER}]
            if p=='Y':return [{'id':s,'name':s,'mimeType':FOLDER} for s in ('TWSE','TPEx','MOPS','FinMind')]
            if p in ('TWSE','TPEx','MOPS','FinMind'):return [{'id':p+'M','name':'2019-01','mimeType':FOLDER}]
            if p=='TWSEM':return [{'id':'a','name':'same.zip','size':'1','mimeType':'application/zip'},{'id':'b','name':'same.zip','size':'1','mimeType':'application/zip'}]
            return []
        with patch('scripts.v093_isolated_duplicate_boundary_audit.ROOT','ROOT'),patch('scripts.v093_isolated_duplicate_boundary_audit.ls',side_effect=ls):
            r=audit_year(Drive(),2019,['2019-01'])
        self.assertEqual(r['duplicates'][0]['status'],'DIFFERENT_CONTENT_QUARANTINE')
        self.assertFalse(r['certified'])
    def test_missing_year_rejected(self):
        with patch('scripts.v093_isolated_duplicate_boundary_audit.ls',return_value=[]):
            with self.assertRaises(ValueError):audit_year(object(),2017,['2017-01'])
if __name__=='__main__':unittest.main()
