"""Independent L1 second-pass: re-inventory actual Drive RAW bytes, retry gaps, and preserve provenance.
Not a numeric/PIT certification. Triggered only after 2015-2000 first-pass cursor is done.
"""
import argparse
import collections
import datetime as dt
import json
import os
from scripts.annual_actual_firstpass import Drive, service
import scripts.v093_history_reverse as engine
import scripts.v093_independent_raw as raw
from scripts.v093_three_year_repair import REPORT_ROOT, stamp

RUN = "L1_RAW_QA_REPAIR_2026_TO_200001_V1"
FIRST = "RAW_201503_TO_200001_V1"
WORKFLOW = "v093-l1-secondpass-qa-repair.yml"

def first_pass_complete():
    d = Drive(service())
    folder = d.find(REPORT_ROOT, FIRST)
    if not folder:
        return False, "FIRST_PASS_CONTROL_NOT_FOUND"
    cursor = engine.getj(d, folder["id"], "CURSOR.json")
    if not cursor:
        return False, "FIRST_PASS_CURSOR_NOT_FOUND"
    if cursor.get("version") != FIRST:
        return False, "FIRST_PASS_VERSION_CONFLICT"
    finished = {x.get("month") for x in cursor.get("finished_months", [])}
    expected = {f"{y}-{m:02d}" for y in range(2000, 2016) for m in range(1, 13)
                if "2000-01" <= f"{y}-{m:02d}" <= "2015-03"}
    complete = bool(cursor.get("done")) and len(finished & expected) == len(expected)
    return complete, ("FIRST_PASS_DONE" if complete else
                      f"FIRST_PASS_PENDING_{len(finished & expected)}_OF_{len(expected)}")

class SecondPass(raw.Independent):
    def report(self, core):
        summary = super().report(core)
        units = list(self.state.get("units", {}).values())
        financial = list(self.state.get("financial_units", {}).values())
        supplements = list(self.state.get("finmind_units", {}).values())
        entries = units + financial + supplements
        errors = self.state.get("inventory_errors", [])
        checks = self.state.get("numeric_checks", {})
        numeric_flags = [v for v in checks.values() if v.get("ohlc_violations") or v.get("null_cells")]
        counts = dict(collections.Counter(e.get("status", "UNKNOWN") for e in entries))
        missing = [e for e in entries if e.get("status") != "SAVED_BASIC_VERIFIED"]
        unresolved_fm = [t for t in self.state.get("finmind_tasks", [])
                         if self.state.get("finmind_units", {}).get(engine.key(t), {}).get("status") != "SAVED_BASIC_VERIFIED"]
        verdict = "PARTIAL_WITH_EXPLICIT_GAPS" if errors or missing or unresolved_fm or numeric_flags else "BASIC_STRUCTURE_PASS_NOT_FULL_QA"
        report = {
            "version": RUN, "month": self.active, "checked_utc": stamp(),
            "status": verdict, "counts": counts, "source_priority": ["TWSE", "TPEx", "MOPS", "FinMind_FREE_GAPS"],
            "inventory_files_checked": len(self.state.get("inventory", {})),
            "inventory_errors": errors, "failed_or_unverified": missing,
            "finmind_pending": unresolved_fm, "price_check_findings": checks,
            "original_raw_immutable": True, "retry_limit_per_unit": 3,
            "market_universe_verified": False, "complete_field_alignment_verified": False,
            "full_numeric_verified": False, "historical_pit_verified": False,
            "production_ready": False,
            "note": "Checks original stored bytes, hashes, formats and basic OHLC; missing or conflicting source data is explicitly recorded. No cross-source silent replacement or synthetic values."
        }
        engine.putj(self.d, self.monthctrl, "SECOND_PASS_AUDIT.json", report)
        summary["second_pass_status"] = verdict
        print("SECOND_PASS_AUDIT " + json.dumps({"month": self.active, "status": verdict,
              "inventory_files": report["inventory_files_checked"], "failed": len(missing),
              "finmind_pending": len(unresolved_fm), "numeric_flags": len(numeric_flags)}, ensure_ascii=False), flush=True)
        return summary

def run(minutes):
    complete, reason = first_pass_complete()
    print("SECOND_PASS_GATE " + reason, flush=True)
    if not complete:
        return
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    raw.RUN = RUN
    raw.WORKFLOW = WORKFLOW
    raw.month_plan = lambda ignored: [f"{y}-{m:02d}" for y in range(today.year, 1999, -1)
                                     for m in range(12, 0, -1)
                                     if (y, m) <= (today.year, today.month)]
    SecondPass(minutes).run()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=40)
    args = p.parse_args()
    run(args.minutes)
