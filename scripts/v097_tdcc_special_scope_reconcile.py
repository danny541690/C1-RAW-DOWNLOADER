#!/usr/bin/env python3
"""v0.97 TDCC 5035 all-file evidence reconciliation and scope disposition.
Not a deletion, not a new market Bronze. All Y-prefix 2025-26 source files
retain original bytes inside v0.97 quarantine, with identity receipts.
Official portal proof on 3 matching day+codes; other files remain
official-provenance-unverified. Do not infer origin from a mere code prefix.
"""
import os,re,json
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call,makefolder
from scripts.v097_tdcc_a3_a5_auto import source_rows,FILE
from scripts.v097_tdcc_code_permutation_diagnosis import pattern
RUN=os.getenv("GITHUB_RUN_ID","manual")
A4="v097_TDCC_A4_V3_CK_L%02d.json"
V4="v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"
PROOF="v097_TDCC_SAME_DATE_COMPARE_43370211117.json"
def now():return datetime.now(timezone.utc).isoformat()
def main():
    api=service()
    manifest,control,qa,bronze=common(api)
    pf=match(api,qa,PROOF)
    if not pf:raise RuntimeError("OFFICIAL_SPOT_PROOF_NOT_PRESENT")
    comp=load_json(api,pf["id"])
    valid={(x["date"],x["code"]):x for x in comp["cases"] if x["state"]=="EXACT_SAME_DATE_CONTENT_MATCH"}
    required={("20260918","YY0064"),("20261002","YFJ1"),("20261016","YMM2")}
    if not required.issubset(valid):raise RuntimeError("EXACT_OFFICIAL_PROOF_GATE_NOT_MET")
    allrows=[];states=Counter();days=Counter();prefixes=Counter();bad=[]
    for lane in range(6):
        a=match(api,control,A4%lane)
        b=match(api,control,V4%lane)
        if not a or not b:raise RuntimeError("MISSING_A4_OR_V4_STAGE_CHECKPOINT_LANE_%02d"%lane)
        a4=load_json(api,a["id"])["done"]
        stage=load_json(api,b["id"])["done"]
        source=source_rows(api,qa,lane)
        ids={r["file_id"] for r in source}
        if not ids.issubset(set(a4)) or not ids.issubset(set(stage)):
            raise RuntimeError("A4_OR_QUARANTINE_INCOMPLETE_LANE_%02d"%lane)
        for r in source:
            fid=r["file_id"];path=str(r.get("source_path") or "")
            fm=FILE.search(path)
            if not fm:
                bad.append({"id":fid,"reason":"FILENAME_NO_VALID_DATE_CODE"});continue
            day,code=fm.group(1),fm.group(2).upper()
            if (a4[fid].get("status")!="HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING"
                or stage[fid].get("status")!="V097_V4_QUARANTINE_SHA_PASS"
                or not stage[fid].get("dest_id") or not stage[fid].get("source_sha256")):
                bad.append({"id":fid,"reason":"A4_QA_OR_QUARANTINE_SHA_NOT_VERIFIED"});continue
            if re.fullmatch(r"\d{4}",code) or re.fullmatch(r"\d{4}[0-9A-Z ]{0,2}",code):
                bad.append({"id":fid,"reason":"POSSIBLE_STOCK_CODE_REQUIRES_MASTER_CHECK"});continue
            proof=valid.get((day,code))
            record={"source_file_id":fid,"source_path":path,
                "security_code_original":code,"file_date":day,
                "code_pattern":pattern(code),
                "source_sha256":stage[fid]["source_sha256"],
                "v097_quarantine_id":stage[fid]["dest_id"],
                "historical_html_table_qa":"A4_TOTALS_MATCH",
                "market_universe":"EXCLUDE_FROM_LISTED_OTC_ORDINARY_STOCK",
                "source_format":"TDCC_HISTORICAL_QUERY_HTML",
                "official_individual_day_proof":"MATCHED_OFFICIAL_ARCHIVE" if proof else "NOT_INDIVIDUALLY_CROSSED",
                "market_bronze_promoted":False,
                "official_security_class":"NOT_CERTIFIED",
                "release_action":"PRESERVE_IN_NONSTOCK_RAW_SIDECAR_DO_NOT_MERGE_TO_4DIGIT"}
            allrows.append(record);states[record["official_individual_day_proof"]]+=1
            days[day]+=1;prefixes[code[:2]]+=1
    if len(allrows)+len(bad)!=5035:raise RuntimeError("TDCC_SOURCE_POPULATION_NOT_5035")
    if bad:raise RuntimeError("TDCC_SCOPE_EXCEPTION_NOT_SAFE_COUNT_"+str(len(bad)))
    if len(allrows)!=5035:raise RuntimeError("INCOMPLETE_SCOPE_CHECK")
    root=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(root)!=1:raise RuntimeError("BRONZE_PARENT_AMBIGUOUS")
    sidecar=makefolder(api,root[0],"00_TDCC_SPECIAL_SECURITY_SIDECAR")
    doc={"schema":"v097_tdcc_5035_scope_manifest_1","run":RUN,"at":now(),
        "source_count":5035,"originals_unchanged":True,
        "all_quarantine_sha_verified":5035,"html_distribution_total_qa_prior_pass":5035,
        "excluded_from_stock_market_raw_universe":5035,
        "formal_bronze_promoted":0,"market_source_data_unavailable":0,
        "same_date_official_sample_count":len(required),
        "same_date_official_samples_verified":len(required),
        "other_individual_origin_certified":False,
        "official_code_standard":"https://schema.nat.gov.tw/lists/75",
        "stock_code_rule":"TWSE/TPEx listed OTC ordinary stock symbol 4 digits; never truncate Y identifiers.",
        "by_date":dict(days),"by_code_prefix":dict(prefixes),"by_official_proof":dict(states),
        "rows":allrows}
    # Complete immutable per-file sidecar plus compact summary, not a market Bronze copy.
    put_once(api,sidecar,"TDCC_5035_SPECIAL_SECURITY_EVIDENCE_%s.json"%RUN,doc)
    compact={k:v for k,v in doc.items() if k!="rows"}
    put_once(api,qa,"TDCC_5035_SPECIAL_SECURITY_SCOPE_SUMMARY_%s.json"%RUN,compact)
    print("TDCC_5035_SCOPE="+json.dumps(compact,ensure_ascii=False),flush=True)
def selftest():
    assert re.fullmatch(r"\d{4}", "YY0037") is None
    assert pattern("YY0037")=="NON_TDCC_GOV_PREFIX_ALPHANUMERIC"
    print("TDCC_SPECIAL_SCOPE_SELFTEST_PASS")
if __name__=="__main__":
    if os.getenv("TDCC_SCOPE_MODE","selftest")=="selftest":selftest()
    else:main()
