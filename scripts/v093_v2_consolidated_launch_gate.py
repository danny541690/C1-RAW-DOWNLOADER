"""Single fail-closed launch readiness decision for JARVIS v0.93.

Never mistake successful metadata or ZIP sampling for complete historical QA.
"""
import json
STAGES=("RAW","QA1","PRICE","FINANCIAL","CHIP")
def decide(evidence):
    checks={
        "scope_322_months":evidence.get("months")==322,
        "source_month_pairs_1288":evidence.get("source_month_pairs")==1288,
        "no_empty_source_months":evidence.get("empty_source_months")==0,
        "no_unresolved_duplicate_names":evidence.get("unresolved_duplicate_names")==0,
        "all_source_months_deep_qa":evidence.get("deep_qa_pass")==1288,
        "pit_verified_all_applicable":evidence.get("pit_verified") is True,
        "numeric_verified_all_applicable":evidence.get("numeric_verified") is True,
        "cross_system_commit_safe":evidence.get("cross_system_commit_safe") is True,
        "durable_resume_all_stages":evidence.get("durable_resume_all_stages") is True,
        "approved_price_adapter":evidence.get("approved_price_adapter") is True,
        "approved_financial_adapter":evidence.get("approved_financial_adapter") is True,
        "approved_chip_adapter":evidence.get("approved_chip_adapter") is True,
        "old_writers_quiesced":evidence.get("old_writers_quiesced") is True,
    }
    return {"decision":"READY_TO_ENABLE_SCHEDULES" if all(checks.values()) else "BLOCKED_KEEP_MANUAL_ONLY","checks":checks,"failed":[k for k,v in checks.items() if not v],"five_stages":STAGES,"production_writes":0}

def evidence_from_inventory(report):
    counts=report.get("counts",{})
    return {"months":report.get("months"),"source_month_pairs":counts.get("source_month_pairs"),"empty_source_months":counts.get("EMPTY_MONTH_FOLDER"),"unresolved_duplicate_names":counts.get("duplicate_names"),"deep_qa_pass":0,"pit_verified":False,"numeric_verified":False,"cross_system_commit_safe":False,"durable_resume_all_stages":False,"approved_price_adapter":False,"approved_financial_adapter":False,"approved_chip_adapter":False,"old_writers_quiesced":False}
