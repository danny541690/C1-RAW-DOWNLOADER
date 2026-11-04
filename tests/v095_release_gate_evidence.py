"""JARVIS v0.95 go-live evidence gate. Read-only and non-destructive.
Writes a machine-readable gate report, never grants production approval from synthetic tests.
"""
import json
import os
from pathlib import Path
import unittest

REQUIRED = [
    ("G0-01", "legacy_main_sha_and_active_runs"),
    ("G0-02", "v093_source_manifest_inventory"),
    ("G0-03", "drive_auth_and_quota_preflight"),
    ("T01", "real_raw_independent_copy_sha"),
    ("T03", "real_daily_and_migration_parallel"),
    ("T05", "distributed_cas_two_runners"),
    ("T08", "real_market_numeric_pit"),
    ("T09", "real_raw_to_silver_gold"),
    ("T10", "release_rollback_and_restore"),
    ("T14", "two_market_sessions_daily"),
    ("T16", "v095_independent_restore"),
]
def evaluate(evidence):
    checks=[]
    for ident, key in REQUIRED:
        entry=evidence.get(key,{})
        passed = entry.get("status")=="PASS" and bool(entry.get("evidence_url")) and bool(entry.get("commit_or_sha"))
        checks.append({"id":ident,"name":key,"status":"PASS" if passed else "BLOCKED",
                       "evidence_url":entry.get("evidence_url") if passed else None,
                       "reason":None if passed else "LIVE_EVIDENCE_MISSING_OR_UNVERIFIED"})
    return {"schema":"JARVIS_V095_RELEASE_GATE_V1",
            "synthetic_ci":"TEST_ONLY",
            "release_approved":all(c["status"]=="PASS" for c in checks),
            "checks":checks}

class GateTests(unittest.TestCase):
    def test_empty_evidence_cannot_release(self):
        report=evaluate({})
        self.assertFalse(report["release_approved"])
        self.assertEqual(sum(x["status"]=="BLOCKED" for x in report["checks"]),len(REQUIRED))
    def test_forged_status_without_evidence_rejected(self):
        self.assertFalse(evaluate({REQUIRED[0][1]:{"status":"PASS"}})["release_approved"])
    def test_evidence_url_without_sha_rejected(self):
        self.assertFalse(evaluate({REQUIRED[0][1]:{"status":"PASS","evidence_url":"https://example.test/evidence"}})["release_approved"])
    def test_all_evidence_explicitly_needed(self):
        all_data={key:{"status":"PASS","evidence_url":"https://example.test/evidence",
                       "commit_or_sha":"a"*64} for _,key in REQUIRED}
        self.assertTrue(evaluate(all_data)["release_approved"])
        all_data[REQUIRED[-1][1]]["status"]="BLOCKED"
        self.assertFalse(evaluate(all_data)["release_approved"])
    def test_missing_evidence_does_not_invent_url(self):
        self.assertIsNone(evaluate({})["checks"][0]["evidence_url"])

if __name__=="__main__":
    unittest.main(verbosity=2, exit=False)
    inp=Path(os.environ.get("JARVIS_GATE_INPUT","/tmp/v095_missing_live_evidence.json"))
    data=json.loads(inp.read_text()) if inp.exists() else {}
    report=evaluate(data)
    output=Path("v095_go_live_gate_report.json")
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("GATE_REPORT="+str(output))
    print("RELEASE_APPROVED="+str(report["release_approved"]).lower())
    print("BLOCKED="+str(sum(x["status"]=="BLOCKED" for x in report["checks"])))
