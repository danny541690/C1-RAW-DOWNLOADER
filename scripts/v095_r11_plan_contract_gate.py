#!/usr/bin/env python3
"""v0.95 R11 no-network risk and pilot plan gate.
No source download, no Drive mutation, no phase flag mutation.
"""
import json,pathlib,sys,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parents[1]
PLAN=ROOT/"config/v095_r11_improvement_and_pilot_plan.json"
FLAGS=ROOT/"governance/v095/PHASE1_FLAGS.json"
R2=ROOT/"config/v095_single_repo_fast_backfill_r2.json"
R7=ROOT/"governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json"

def evaluate(plan,flags,r2,accepted):
 errors=[]
 def ck(cond,reason):
  if not cond:errors.append(reason)
 a=plan["architecture"];r=plan["rules"]
 ck(len(plan["issues"])==12,"R11_ISSUE_CARDINALITY")
 ck(len(set(x["id"] for x in plan["issues"]))==12,"R11_ISSUE_ID_DUPLICATION")
 ck({x["priority"] for x in plan["issues"]}=={"P0","P1","P2"},"R11_PRIORITY_CLASS")
 ck(a["controller_count"]==1 and a["logical_ingest_slots"]==16,"R11_CONTROLLER_SLOT_TOPOLOGY")
 ck(a["qa_stage_categories"]=={"bronze":6,"silver":4,"gold":4},"R11_QUALITY_CATEGORY_TOPOLOGY")
 ck(sum(a["qa_stage_categories"].values())==14 and a["logical_ingest_slots"]!=14,"R11_INGEST_VS_QA_CONFUSION")
 ck(a["release_layers"]["gold"]=="VALID_FORMULA_PLUS_POINT_IN_TIME_LINEAGE","R11_GOLD_PIT_NOT_GATED")
 ck(all(x["id"] and x["problem"] and x["root_cause"] and x["remediation"] and x["acceptance"] for x in plan["issues"]),"R11_ISSUE_INCOMPLETE")
 ck([x["phase"] for x in plan["trial_plan"]]==["T0","T1","T2","T3","T4"],"R11_PILOT_PHASES")
 ck(plan["trial_plan"][0]["units"]==0 and plan["trial_plan"][-1]["units"]<=6,"R11_UNBOUNDED_CANARY")
 ck(r["read_only_plan"] is True and r["no_unverified_data_mutation"] is True,"R11_MUTATION_NOT_GATED")
 ck(r["full_history_bulk_enabled"] is False and r["release_approved"] is False,"R11_UNSAFE_PLAN_RELEASE")
 ck(flags.get("BULK_COPY_APPROVED") is False and flags.get("RELEASE_APPROVED") is False,"R11_UNSAFE_EXISTING_RELEASE")
 ck(r2["mode"]=="PLAN_AND_GATE_ONLY" and r2["acceptance"]["historical_bulk_start_allowed"] is False,"R11_R2_BULK_CONFLICT")
 ck(r["unknown_denominator"]=="UNKNOWN_NOT_ZERO_OR_FULL","R11_UNKNOWN_COVERAGE_MISSTATED")
 ck(len(accepted["immutable_receipts"])==12,"R11_PRIOR_ACCEPTANCE_COUNT")
 ck(all(x.get("content_sha256") and x.get("digest_scope") and x.get("evidence_run_id") for x in accepted["immutable_receipts"]),"R11_ACCEPTANCE_SHA_PROVENANCE")
 ck(r["transient_retry_count"]==3 and r["nontransient"]=="QUARANTINE_NO_SPIN","R11_BAD_RETRY_POLICY")
 ck(plan["source_scope"]["historical_eligible_dates_only"] is True,"R11_FUTURE_DATE_RISK")
 return {"schema":"JARVIS_V095_R11_SPEC_GATE_V1","status":"PASS_NO_NETWORK_PILOT_SPEC" if not errors else "FAIL_CONTRACT",
 "controls":18,"issues":len(plan["issues"]),"pilot_phases":len(plan["trial_plan"]),
 "ingest_slots":a["logical_ingest_slots"],"qa_categories":sum(a["qa_stage_categories"].values()),
 "preexisting_scoped_receipts":len(accepted["immutable_receipts"]),
 "bulk_history_download_started":False,"production_release_approved":False,
 "error_count":len(errors),"errors":errors,
 "not_proven":["LIVE_BRONZE_WRITE","REAL_CAS_FENCING","EXPECTED_DENOMINATOR","443_FORMULA_PIT","FULL_BIDIRECTIONAL_LINEAGE"],
 "next_allowed_phase":"T1_READ_ONLY_MANIFEST_ONLY"}
def main():
 vals=[json.loads(x.read_text()) for x in (PLAN,FLAGS,R2,R7)]
 out=evaluate(*vals)
 dst=ROOT/"r11_pilot_contract";dst.mkdir(exist_ok=True)
 (dst/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(out,ensure_ascii=False))
 return 0 if not out["errors"] else 2
if __name__=="__main__":sys.exit(main())
