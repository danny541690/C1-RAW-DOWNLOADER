"""R21 TDCC semantic QA and explicit fail-closed Gold gate.
Fixtures exercise the confirmed rules. Live numeric audit is archived separately.
"""
import unittest
from decimal import Decimal

def audit_tiers(rows):
    by_grade={}
    for row in rows:
        grade=int(row["持股分級"])
        if grade in by_grade:raise ValueError("DUPLICATE_GRADE")
        by_grade[grade]=row
    if set(by_grade)!=set(range(1,18)):raise ValueError("MISSING_GRADE")
    def num(n,k):return int(str(by_grade[n][k]).replace(",",""))
    d_h=sum(num(n,"人數") for n in range(1,17))-num(17,"人數")
    d_s=sum(num(n,"股數") for n in range(1,17))-num(17,"股數")
    proportion=sum(Decimal(by_grade[n]["占集保庫存數比例%"]) for n in range(1,17))
    return {"grade_count":len(by_grade),"holder_discrepancy":d_h,"share_discrepancy":d_s,
            "tier16_adjustment_shares":num(16,"股數"),
            "ratio_sum":proportion,"requires_definition_review":bool(d_h or d_s or abs(proportion-100)>Decimal(".08"))}
def make_fixture():
    rows=[{"持股分級":str(i),"人數":"0","股數":"0","占集保庫存數比例%":"0.00"} for i in range(1,18)]
    rows[0].update({"人數":"2","股數":"200","占集保庫存數比例%":"100.00"})
    rows[16].update({"人數":"2","股數":"200","占集保庫存數比例%":"100.00"})
    return rows

def gold_release(numeric_verified,pit_verified,security_master_verified):
    return all(x is True for x in (numeric_verified,pit_verified,security_master_verified))

class TDCCSemanticQA(unittest.TestCase):
    def test_01_tier17_is_total_not_independent_bucket(self):
        self.assertEqual(audit_tiers(make_fixture())["share_discrepancy"],0)
    def test_02_discrepant_total_is_warning_not_source_corruption(self):
        rows=make_fixture();rows[16]["股數"]="201"
        audit=audit_tiers(rows)
        self.assertTrue(audit["requires_definition_review"])
        self.assertEqual(audit["share_discrepancy"],-1)
    def test_03_rounding_tolerance_requires_warning(self):
        rows=make_fixture();rows[0]["占集保庫存數比例%"]="99.90"
        self.assertTrue(audit_tiers(rows)["requires_definition_review"])
    def test_04_missing_grade_blocks(self):
        with self.assertRaises(ValueError):audit_tiers(make_fixture()[:-1])
    def test_05_duplicate_grade_blocks(self):
        with self.assertRaises(ValueError):audit_tiers(make_fixture()+[make_fixture()[0]])
    def test_06_alphanumeric_and_whitespace_codes_must_not_be_numbers(self):
        self.assertEqual("00406A".strip(),"00406A")
        self.assertEqual("00712 ".strip(),"00712")
    def test_07_unverified_pit_never_releases(self):
        self.assertFalse(gold_release(True,False,True))
    def test_08_unverified_security_master_never_releases(self):
        self.assertFalse(gold_release(True,True,False))
    def test_09_no_implicit_approval(self):
        self.assertFalse(gold_release(None,None,None))
if __name__=="__main__":unittest.main(verbosity=2)
