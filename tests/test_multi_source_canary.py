import unittest
import json
from scripts.multi_source_canary import inspect_tpex,inspect_mops

class MultiSourceCanary(unittest.TestCase):
    def test_tpex_dates(self):
        x=inspect_tpex(json.dumps({"aaData":[["113/01/02",1],["113/01/03",2]]}).encode())
        self.assertEqual(x["records"],2)
    def test_tpex_wrong_period(self):
        with self.assertRaises(ValueError): inspect_tpex(json.dumps({"aaData":[["114/01/02"]]}).encode())
    def test_mops_html_presence(self):
        x=inspect_mops(("<table><tr><td>營業收入</td></tr></table>"+"x"*1100).encode("big5"))
        self.assertFalse(x["pit_verified"])
    def test_mops_rejects_short(self):
        with self.assertRaises(ValueError): inspect_mops(b"no table")
