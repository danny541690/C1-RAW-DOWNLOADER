import unittest
from unittest.mock import patch
from scripts.v093_isolated_full_history_inventory import inventory

class FullHistoryInventoryTests(unittest.TestCase):
    def test_missing_and_present_are_not_certified(self):
        def ls(d,parent):
            if parent=='ROOT':
                return [{'id':'Y','name':'2000','mimeType':'application/vnd.google-apps.folder'}]
            if parent=='Y':
                return [{'id':'S','name':'TWSE','mimeType':'application/vnd.google-apps.folder'}]
            if parent=='S':
                return [{'id':'M','name':'2000-01','mimeType':'application/vnd.google-apps.folder'}]
            return []
        with patch('scripts.v093_isolated_full_history_inventory.ROOT','ROOT'),patch('scripts.v093_isolated_full_history_inventory.ls',side_effect=ls):
            r=inventory(object(),2000,2000,'2000-01')
        self.assertEqual(r['month_count'],1)
        self.assertEqual(r['source_month_folder_present'],1)
        self.assertEqual(r['source_month_folder_missing'],3)
        self.assertEqual(r['certified_months'],0)
        self.assertEqual(r['months']['2000-01']['TWSE'],'MONTH_FOLDER_PRESENT_UNVERIFIED')
    def test_latest_month_caps_future(self):
        with patch('scripts.v093_isolated_full_history_inventory.ls',return_value=[]):
            r=inventory(object(),2026,2026,'2026-10')
        self.assertEqual(r['month_count'],10)
        self.assertEqual(r['source_month_total'],40)
    def test_range_rejects_invalid(self):
        with self.assertRaises(ValueError):inventory(object(),1999,2026)
if __name__=='__main__':unittest.main()
