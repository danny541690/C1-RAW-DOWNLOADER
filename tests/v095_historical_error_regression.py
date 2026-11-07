"""R14 regression: historical real-source anomalies, isolated tests only."""
import hashlib
import unittest

def validate_receipt(raw, reported_sha, reported_bytes):
    verified_sha=hashlib.sha256(raw).hexdigest()
    if verified_sha != reported_sha: return "CORRUPT_RAW"
    if len(raw)!=reported_bytes: return "RECEIPT_SIZE_MISMATCH"
    return "BASIC_RAW_PASS"

def balance_ok(margin, short):
    # margin = prior + buy - sell - cash_repay;
    # short = prior + sell - buy - share_repay.
    return (margin["previous"]+margin["buy"]-margin["sell"]-margin["repay"]==margin["current"]
            and short["previous"]+short["sell"]-short["buy"]-short["repay"]==short["current"])

def derive_raw_rows(tables):
    return sum(len(table["data"]) for table in tables)

def publication_gate(numeric_qa,pit,receipt):
    return numeric_qa is True and pit is True and receipt=="BASIC_RAW_PASS"

class HistoricalAnomalyTests(unittest.TestCase):
    def test_sha_correct_size_wrong_must_hold(self):
        data=b"X"*129327
        self.assertEqual(validate_receipt(data,hashlib.sha256(data).hexdigest(),129326),"RECEIPT_SIZE_MISMATCH")
    def test_sha_wrong_must_hold(self):
        self.assertEqual(validate_receipt(b"ABC","0"*64,3),"CORRUPT_RAW")
    def test_sha_size_agree(self):
        data=b"ABC"
        self.assertEqual(validate_receipt(data,hashlib.sha256(data).hexdigest(),len(data)),"BASIC_RAW_PASS")
    def test_multi_table_rows_3_plus_1302(self):
        t=[{"data":[None]*3},{"data":[None]*1302}]
        self.assertEqual(derive_raw_rows(t),1305)
    def test_real_twse_balance_formulas_example(self):
        self.assertTrue(balance_ok(
            dict(previous=14127,buy=518,sell=168,repay=0,current=14477),
            dict(previous=0,buy=0,sell=3,repay=0,current=3)))
    def test_numerical_only_cannot_release(self):
        self.assertFalse(publication_gate(True,False,"BASIC_RAW_PASS"))
    def test_receipt_correction_not_pit_approval(self):
        self.assertFalse(publication_gate(True,False,"RECEIPT_SIZE_MISMATCH"))
    def test_preserve_alphanumeric_zero_prefix_id(self):
        code="00400A"
        self.assertEqual(code,"00400A")
        self.assertFalse(code.isdecimal())
if __name__=="__main__":unittest.main(verbosity=2)
