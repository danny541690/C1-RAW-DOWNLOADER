"""Independent L1 second-pass: re-inventory actual Drive RAW bytes, retry gaps, and preserve provenance.
Not a numeric/PIT certification. Independently audits latest Taiwan month down to 2015-04.
"""
import argparse
import collections
import datetime as dt
import json
import os
from scripts.annual_actual_firstpass import Drive, service
import scripts.v093_history_reverse as engine
import scripts.v093_independent_raw as raw
from scripts.v093_three_year_repair import stamp
from scripts.v093_folder_registry import FolderRegistry

RUN = "L1_RAW_QA_REPAIR_LATEST_TO_201504_V2"
END_MONTH = "2015-04"
WORKFLOW = "v093-l1-secondpass-qa-repair.yml"

class SecondPass(raw.Independent):
    expected_end_month = END_MONTH
    def __init__(self, minutes):
        super().__init__(minutes)
        # The first-pass 2015-03..2000-01 may still be running.
        # Isolate this pass's folder registry writes from the other run.
        self.registry = FolderRegistry(self.d, '10_k6r3pRGKYUp5YbyD3UA1oWw6DngHlO',
                                       namespace='L1_SECOND_PASS_201504_PLUS')
        assert self.months[-1] == END_MONTH
        assert len(self.months) == len(set(self.months))
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
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    start_month = f"{today.year}-{today.month:02d}"
    months = [f"{y}-{m:02d}" for y in range(today.year, 2014, -1)
              for m in range(12, 0, -1)
              if END_MONTH <= f"{y}-{m:02d}" <= start_month]
    assert months and months[0] == start_month and months[-1] == END_MONTH
    assert all(months[i] > months[i+1] for i in range(len(months)-1))
    raw.RUN = RUN
    raw.WORKFLOW = WORKFLOW
    raw.month_plan = lambda ignored: list(months)
    print("SECOND_PASS_SCOPE " + json.dumps({"start": start_month, "end": END_MONTH,
          "months": len(months), "first_pass_wait": False}), flush=True)
    SecondPass(minutes).run()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=40)
    args = p.parse_args()
    run(args.minutes)
