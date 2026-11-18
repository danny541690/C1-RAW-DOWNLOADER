"""R3 cross-version snapshot audit contract tests with synthetic fixtures only."""
import unittest
from copy import deepcopy
from scripts.v097_r3_snapshot_audit import audit_snapshots
from scripts.v097_r3_gate_core import SOURCES, COHORT
COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}

def snapshots():
    a={"cohort":COHORT,"run":"synthetic-r1","ready":0,"silver_materialized":0,"gold_materialized":0,
       "status":{"PENDING":COHORT,"NOT_EVALUATED":0},"evaluated":COHORT,
       "sources":[{"source":s,"cohort":n,"status":{"PENDING":n}} for s,n in COUNTS.items()]}
    b={"cohort":COHORT,"run":"synthetic-v3","schema_ready_certified":0,"silver_materialized":0,"gold_materialized":0,
       "checked":COHORT,"not_checked":0,"statuses":{"EVIDENCE_PENDING":COHORT,"NOT_CHECKED":0},
       "sources":[{"source":s,"cohort":n,"checked":n} for s,n in COUNTS.items()]}
    return a,b

class SnapshotTests(unittest.TestCase):
    def test_matching_counts_but_different_progress_not_additive(self):
        a,b=snapshots()
        a["status"]={"PENDING":50000,"NOT_EVALUATED":24750}
        a["evaluated"]=50000
        done=0
        for s in a["sources"]:
            take=min(s["cohort"],50000-done)
            s["status"]={"PENDING":take,"NOT_EVALUATED":s["cohort"]-take}
            done+=take
        b["checked"]=40000
        b["not_checked"]=34750
        b["statuses"]={"EVIDENCE_PENDING":40000,"NOT_CHECKED":34750}
        done=0
        for s in b["sources"]:
            take=min(s["cohort"],40000-done)
            s["checked"]=take
            done+=take
        out=audit_snapshots(a,b)
        self.assertTrue(out["pass"],out)
        self.assertEqual(out["r1"]["evaluated"],50000)
        self.assertEqual(out["v3"]["checked"],40000)
    def test_rejects_source_census_drift(self):
        a,b=snapshots()
        b["sources"][0]["cohort"]-=1
        self.assertIn("CROSS_VERSION_COHORT_DIVERGENCE",audit_snapshots(a,b)["problems"])
    def test_rejects_false_ready(self):
        a,b=snapshots()
        b["schema_ready_certified"]=1
        self.assertFalse(audit_snapshots(a,b)["pass"])
    def test_rejects_silver_gold_side_effect(self):
        a,b=snapshots()
        a["gold_materialized"]=1
        self.assertIn("R1_UNAUTHORIZED_MATERIALIZATION",audit_snapshots(a,b)["problems"])
    def test_rejects_missing_source_and_progress_mismatch(self):
        a,b=snapshots()
        b["sources"].pop()
        x=audit_snapshots(a,b)
        self.assertFalse(x["pass"])
        self.assertIn("V3_SOURCE_SET_MISMATCH",x["problems"])

if __name__=="__main__": unittest.main()
