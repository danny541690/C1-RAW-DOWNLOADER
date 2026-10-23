import json
import unittest
from scripts.v093_official_content_audit import audit_rows,value_digest

class RowAuditTests(unittest.TestCase):
    def raw(self,rows=None,extra=None):
        obj={'stat':'OK','fields':['證券代號','開盤價','最高價','最低價','收盤價','成交股數'],
             'data':rows or [['2330','100','110','90','105','1000']]}
        obj.update(extra or {});return json.dumps(obj).encode()
    def job(self):return {'category':'prices_indices'}
    def test_price_rows_and_quantity_are_actually_checked(self):
        out=audit_rows(self.raw(),self.job())
        self.assertEqual(out['ohlc_rows_checked'],1);self.assertEqual(out['numeric_cells_checked'],1)
    def test_invalid_price_relationship_is_rejected(self):
        with self.assertRaises(ValueError):audit_rows(self.raw([['2330','100','95','90','105','1000']]),self.job())
    def test_negative_volume_is_rejected(self):
        with self.assertRaises(ValueError):audit_rows(self.raw([['2330','100','110','90','105','-1']]),self.job())
    def test_duplicate_security_is_rejected(self):
        row=['2330','100','110','90','105','1000']
        with self.assertRaises(ValueError):audit_rows(self.raw([row,row]),self.job())
    def test_nontrade_prices_are_not_accepted_as_verified(self):
        out=audit_rows(self.raw([['2330','--','--','--','--','0']]),self.job())
        self.assertIn('NO_VALID_TRADE_PRICE_REQUIRES_REVIEW',out['unverified'])
    def test_wrapper_timestamp_does_not_create_false_value_revision(self):
        self.assertEqual(value_digest(self.raw(extra={'updated':'a'})),value_digest(self.raw(extra={'updated':'b'})))
    def test_changed_source_value_is_detected(self):
        self.assertNotEqual(value_digest(self.raw()),value_digest(self.raw([['2330','100','110','90','104','1000']])))

if __name__=='__main__':unittest.main()
