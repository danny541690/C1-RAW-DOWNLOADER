#!/usr/bin/env python3
"""JARVIS v0.97 MOPS numeric accounting identity QA for staged, parsed originals.
Checks cashflow opening + period movement = closing per company, exact Decimal.
A pass validates one identity only, NEVER source publication or full Bronze/PIT.
"""
import os,json,hashlib
from decimal import Decimal,InvalidOperation
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call
from scripts.v097_mops_html_matrix_recovery import candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("MOPS_ID_LANE","0"))
NAME="v097_MOPS_CASHFLOW_IDENTITY_V1"
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(doc):
    if doc.get("dataset_type")!="MOPS_FINANCIAL_HTML_MATRIX" or doc.get("unit")!="TWD_THOUSAND":
        return "BAD_FORMAT_OR_UNIT",{}
    expected_keys=["期初現金及約當現金餘額","本期現金及約當現金增加（減少）數","期末現金及約當現金餘額"]
    vals={}
    for label in expected_keys:
        found=[r for r in doc.get("rows",[]) if r.get("account")==label]
        if len(found)!=1:return "ACCOUNT_IDENTITY_NOT_APPLICABLE",{"reason":"MISSING_OR_DUPLICATE_"+label}
        vals[label]=found[0].get("values_thousand_twd",[])
    n=len(doc.get("companies",[]))
    if n<1 or any(len(v)!=n for v in vals.values()):return "BAD_MATRIX_SHAPE",{}
    tested=unavailable=0;fail=[]
    for i in range(n):
        triples=[vals[k][i] for k in expected_keys]
        if any(v is None for v in triples):unavailable+=1;continue
        try:
            before,change,after=map(Decimal,triples)
            if not all(x.is_finite() for x in [before,change,after]):raise ValueError("NAN")
            tested+=1
            if before+change!=after:fail.append({"company":doc["companies"][i]["code"],"difference_thousand":str(before+change-after)})
        except Exception:
            fail.append({"company":doc["companies"][i]["code"],"difference_thousand":"INVALID_NUMBER"})
    details={"tested_companies":tested,"missing_inputs":unavailable,
             "mismatch_count":len(fail),"mismatch_examples":fail[:8]}
    if fail:return "CASHFLOW_ACCOUNTING_IDENTITY_FAIL",details
    if tested<1:return "ACCOUNT_IDENTITY_NOT_APPLICABLE",details
    return "CASHFLOW_IDENTITY_PASS_PIT_PENDING",details
def one(api,sourceid,record):
    out={"file_id":sourceid,"bronze_certified":False,"pit_certified":False}
    if record.get("status")!="MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING":
        out["state"]="PARSER_NOT_PASSED";return out
    dest=record.get("parsed_dest_id")
    if not dest:
        out["state"]="MISSING_PARSED_DATA_ID";return out
    try:
        b=call(lambda:api.files().get_media(fileId=dest))
        obj=json.loads(b.decode("utf-8"))
        if obj.get("source_file_id")!=sourceid:raise ValueError("SOURCE_ID_MISMATCH")
        if obj.get("source_year")!=str(obj.get("source_month",""))[:4]:
            raise ValueError("PERIOD_YEAR_MISMATCH")
        status,detail=check(obj)
        out.update(state=status,parsed_sha256=sha(b),parsed_dest_id=dest,details=detail)
    except Exception as exc:out.update(state="READ_OR_PROVENANCE_FAIL",error=type(exc).__name__+":"+str(exc)[:150])
    return out
def lane_run(api,lane):
    m,c,q,_=common(api)
    allowed={r["file_id"] for r,_,_ in candidates(api,m,c,lane)}
    f=match(api,c,"v097_MOPS_HTML_MATRIX_QA_V1_CK_%02d.json"%lane)
    if not f:raise RuntimeError("MOPS_CHECKPOINT_MISSING")
    d=load_json(api,f["id"]).get("done",{})
    if not set(d).issubset(allowed):raise RuntimeError("MOPS_CHECKPOINT_ORPHAN")
    ckname=NAME+"_CK_%02d.json"%lane
    old=match(api,c,ckname)
    ck=load_json(api,old["id"]) if old else {"schema":"v097_cashflow_qa_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_cashflow_qa_ck_1" or ck.get("lane")!=lane:raise RuntimeError("CASHFLOW_CHECKPOINT_CONFLICT")
    todo=[(fid,v) for fid,v in d.items() if fid not in ck["done"]][:45]
    offset=len(ck["done"]);name="%s_%s_L%02d_O%04d.json"%(NAME,RUN,lane,offset)
    receipt=match(api,q,name)
    if receipt:results=load_json(api,receipt["id"])["rows"]
    else:
        results=[one(api,fid,detail) for fid,detail in todo]
        put_once(api,q,name,{"schema":"v097_cashflow_qa_receipt_1","run":RUN,"lane":lane,"rows":results,
            "market_bronze_promotions":0})
    for r in results:ck["done"][r["file_id"]]={"state":r["state"],"parsed_dest_id":r.get("parsed_dest_id")}
    upsert(api,c,ckname,dict(ck,last_receipt=name,updated_at=now()))
    print("CASHFLOW_IDENTITY_LANE="+json.dumps({"lane":lane,"checked":len(ck["done"]),
       "parser_processed":len(d),"remaining":len(d)-len(ck["done"]),
       "states":dict(Counter(x["state"] for x in ck["done"].values()))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api);state=Counter();processed=0
    for lane in range(6):
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        if f:
            d=load_json(api,f["id"]);processed+=len(d["done"]);state.update(x["state"] for x in d["done"].values())
    report={"schema":"v097_cashflow_identity_qa_summary_1","run":RUN,
        "checked":processed,"by_state":dict(state),
        "accounting_identity_pass":state["CASHFLOW_IDENTITY_PASS_PIT_PENDING"],
        "formal_bronze_certified":0,"pit_pending":True}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,report)
    print("CASHFLOW_IDENTITY_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    def d(v):return {"dataset_type":"MOPS_FINANCIAL_HTML_MATRIX","unit":"TWD_THOUSAND",
      "companies":[{"code":"1234"}],
      "rows":[{"account":k,"values_thousand_twd":[v[i]]} for i,k in enumerate([
      "期初現金及約當現金餘額","本期現金及約當現金增加（減少）數","期末現金及約當現金餘額"])]}
    assert check(d(["100","-20","80"]))[0]=="CASHFLOW_IDENTITY_PASS_PIT_PENDING"
    assert check(d(["100","-20","81"]))[0]=="CASHFLOW_ACCOUNTING_IDENTITY_FAIL"
    print("CASHFLOW_IDENTITY_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("CASHFLOW_ID_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise RuntimeError("UNKNOWN_CASHFLOW_MODE")
