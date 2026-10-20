"""JARVIS L1 third-pass RAW repair. Strictly gated by second-pass monthly audit.

No claims of cross-source numeric or PIT verification. Alternate public sources are
discovery candidates until an explicit field/unit/PIT mapping and tests are approved.
"""
import argparse
import datetime as dt
import json
import os
from scripts.annual_actual_firstpass import Drive, service
from scripts.v093_three_year_repair import REPORT_ROOT, stamp
import scripts.v093_history_reverse as engine
import scripts.v093_independent_raw as raw
from scripts.v093_folder_registry import FolderRegistry

THIRD = "L1_RAW_THIRD_PASS_GATED_REPAIR_V1"
SECOND = "L1_RAW_QA_REPAIR_LATEST_TO_201504_V2"
WORKFLOW = "v093-l1-thirdpass-gated-repair.yml"
END = "2015-04"
VALID_SECOND = {"PARTIAL_WITH_EXPLICIT_GAPS", "BASIC_STRUCTURE_PASS_NOT_FULL_QA"}
OTHER_SOURCE_CANDIDATES = [
    {"name": "TWSE OpenAPI / government open-data mirrors", "status": "NOT_APPROVED_FOR_FIELD_REPLACEMENT"},
    {"name": "TPEx public open-data endpoints", "status": "NOT_APPROVED_FOR_FIELD_REPLACEMENT"},
    {"name": "TAIFEX official market data (only applicable datasets)", "status": "NOT_EQUIVALENT_TO_STOCK_FIELDS"},
    {"name": "Other public repositories / licensed open datasets", "status": "REQUIRES_SOURCE_TERMS_AND_SCHEMA_VALIDATION"},
]

def months_through(today):
    start = f"{today.year}-{today.month:02d}"
    return [f"{y}-{m:02d}" for y in range(today.year, 2014, -1)
            for m in range(12, 0, -1) if END <= f"{y}-{m:02d}" <= start]

def eligible_month(d, second_control, month, finished):
    if month not in finished:
        return None
    month_folder = d.find(second_control, month)
    if not month_folder or month_folder["mimeType"] != "application/vnd.google-apps.folder":
        return None
    audit = engine.getj(d, month_folder["id"], "SECOND_PASS_AUDIT.json")
    if not audit or audit.get("month") != month or audit.get("version") != SECOND:
        return None
    if audit.get("status") not in VALID_SECOND:
        return None
    return audit

class ThirdPass(raw.Independent):
    def __init__(self, minutes, month, second_audit):
        self.expected_end_month = month
        self.second_audit = second_audit
        super().__init__(minutes)
        self.registry = FolderRegistry(self.d, '10_k6r3pRGKYUp5YbyD3UA1oWw6DngHlO',
                                       namespace='L1_THIRD_PASS_GATED_REPAIR')
        if self.months != [month]:
            raise ValueError("THIRD_PASS_MONTH_PLAN_CONFLICT")

    def report(self, core):
        summary = super().report(core)
        rows = list(self.state.get("units", {}).values()) + list(self.state.get("financial_units", {}).values()) + list(self.state.get("finmind_units", {}).values())
        unresolved = [x for x in rows if x.get("status") != "SAVED_BASIC_VERIFIED"]
        audit = {
            "version": THIRD, "month": self.active, "checked_utc": stamp(),
            "second_pass_gate": {"version": SECOND, "month": self.second_audit["month"],
                "status": self.second_audit["status"], "checked_utc": self.second_audit.get("checked_utc")},
            "source_priority": ["TWSE", "TPEx", "MOPS", "FinMind_FREE_GAP_ONLY"],
            "alternative_public_source_registry": OTHER_SOURCE_CANDIDATES,
            "alternative_source_auto_substitution_enabled": False,
            "existing_raw_immutable": True, "retry_limit_per_unit": 3,
            "unresolved_units": len(unresolved),
            "inventory_errors": len(self.state.get("inventory_errors", [])),
            "finmind_tasks": len(self.state.get("finmind_tasks", [])),
            "numeric_verified": False, "historical_pit_verified": False,
            "cross_source_equivalence_verified": False, "production_ready": False,
            "status": "PARTIAL_WITH_EXPLICIT_GAPS" if unresolved or self.state.get("inventory_errors") else "BASIC_STRUCTURE_PASS_NOT_FULL_QA",
            "note": "Actual RAW byte re-inventory and official/FinMind bounded gap retries. Other open-source replacements must first pass per-dataset source/schema/unit/date/PIT approval; no silent mixing."
        }
        engine.putj(self.d, self.monthctrl, "THIRD_PASS_AUDIT.json", audit)
        summary["third_pass_status"] = audit["status"]
        return summary

    def disable_finished_schedule(self):
        # This invocation handles one gated month; the workflow remains enabled for later eligible months.
        return

def run(minutes):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    d = Drive(service())
    second = d.find(REPORT_ROOT, SECOND)
    if not second:
        print("THIRD_PASS_WAIT_SECOND_CONTROL_MISSING", flush=True)
        return
    second_control = second["id"]
    cursor = engine.getj(d, second_control, "CURSOR.json") or {}
    finished = {x["month"] for x in cursor.get("finished_months", [])
                if x.get("month") and x.get("second_pass_status") in VALID_SECOND}
    # The second-pass cursor may be committed before the audit status field; the audit is still mandatory.
    finished |= {x["month"] for x in cursor.get("finished_months", [])
                 if x.get("month") and x.get("phase") == "PRIMARY_SAVED_WITH_EXPLICIT_GAPS"}
    third_control = d.folder(REPORT_ROOT, THIRD)
    third_cursor = engine.getj(d, third_control, "THIRD_CURSOR.json") or {
        "version": THIRD, "completed": {}, "created_utc": stamp()}
    if third_cursor.get("version") != THIRD:
        raise ValueError("THIRD_CURSOR_VERSION_CONFLICT")
    chosen = None
    audit = None
    for month in months_through(today):
        if third_cursor["completed"].get(month, {}).get("done"):
            continue
        audit = eligible_month(d, second_control, month, finished)
        if audit is not None:
            chosen = month
            break
        # Strict descending chronology; don't skip a month still awaiting second-pass audit.
        print("THIRD_PASS_WAIT_SECOND_AUDIT " + month, flush=True)
        break
    if chosen is None:
        print("THIRD_PASS_NO_ELIGIBLE_MONTH", flush=True)
        return
    print("THIRD_PASS_GATE_PASS " + json.dumps({"month": chosen, "second_status": audit["status"]}), flush=True)
    scoped = THIRD + "_" + chosen.replace("-", "")
    raw.RUN = scoped
    raw.WORKFLOW = WORKFLOW
    raw.month_plan = lambda ignored: [chosen]
    job = ThirdPass(minutes, chosen, audit)
    job.run()
    if job.checkpoint.get("month_index", 0) >= 1:
        result = engine.getj(job.d, job.d.folder(job.control, chosen), "THIRD_PASS_AUDIT.json")
        if result is None:
            raise ValueError("THIRD_PASS_AUDIT_NOT_SAVED")
        third_cursor["completed"][chosen] = {"done": True, "status": result["status"],
                                               "report_folder_id": job.monthctrl,
                                               "updated_utc": stamp()}
        third_cursor["updated_utc"] = stamp()
        engine.putj(d, third_control, "THIRD_CURSOR.json", third_cursor)
        print("THIRD_PASS_MONTH_CHECKPOINT_SAVED " + chosen, flush=True)
    else:
        print("THIRD_PASS_MONTH_INCOMPLETE_RESUME_NEXT_RUN " + chosen, flush=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=40)
    a = p.parse_args()
    run(a.minutes)
