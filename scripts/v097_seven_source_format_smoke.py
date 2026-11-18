#!/usr/bin/env python3
"""Seven-source, six-file-per-source read-only historic-template smoke test.
Only FORMAT_CANDIDATE is emitted: never official G2 PASS, never Silver/Gold.
"""
import collections,datetime,hashlib,io,json,os,sys,zipfile
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_two_source_pilot_g2 import ordered,kind,era,inspect_blob,MAX_FILE
from scripts.v097_g2g3_native_headers import header_for
from scripts.v097_v3_contract_registry import infer,REGISTRY_VERSION
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_g2g3_full_native_validation import full_scan
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind")
SCHEMA="v097_seven_source_format_smoke_v1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
N=max(1,min(12,int(os.getenv("SEVEN_SMOKE_N","6"))))
def sha(v):return hashlib.sha256(v).hexdigest()
def evaluate_native(blob,path,source,historical):
    if source in ("TDCC","TAIFEX"):
        return inspect_blob(blob,path,source,historical)
    if kind(path) in (".csv",".txt"):
        from scripts.v097_two_source_pilot_g2 import csv_evidence
        return csv_evidence(blob,path,source,historical)
    if kind(path)==".zip":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos=[x for x in z.infolist() if not x.is_dir()]
            if not infos or len(infos)>1000 or sum(x.file_size for x in infos)>64*1024*1024:
                return {"status":"ZIP_EMPTY_OR_RESOURCE_HOLD","candidate":False}
            members=[]
            for x in infos[:8]:
                if x.file_size>MAX_FILE or x.filename.startswith("/") or ".." in x.filename.replace("\\","/").split("/"):
                    return {"status":"ZIP_MEMBER_UNSAFE_OR_LARGE","candidate":False}
                content=z.read(x)
                ev=evaluate_native(content,x.filename,source,historical) if kind(x.filename)!=".zip" else {"status":"NESTED_ZIP_PENDING","candidate":False}
                members.append({"path":x.filename,"member_sha":sha(content),"result":ev})
            candidate=(len(infos)<=len(members) and all(v["result"].get("candidate") for v in members))
            return {"status":"STRUCTURE_CANDIDATE" if candidate else "ZIP_MEMBER_CONTRACT_PENDING",
                    "candidate":candidate,"members":members,"member_count":len(infos)}
    h=header_for(blob,path,source)
    header=h.get("header",[])
    proof=infer(source,header,historical,metadata=h.get("source_metadata"))
    full=full_scan(blob,path,source,historical,header) if kind(path) in (".json",".jsonl") else {}
    candidate=proof.get("status")=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED" and (
      not full or full.get("status")=="FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED")
    return {"status":"STRUCTURE_CANDIDATE" if candidate else "DATASET_OR_NATIVE_FORMAT_PENDING",
            "candidate":candidate,"format":h.get("format"),"header":header,
            "contract":proof,"full_shape":full}
def audit(row,source,api,call):
    path=row.get("source_path","")
    res={"source_id":row["source_id"],"source":source,"path":path,
         "sha":row["source_sha256"],"era":era(row,source),"file_format":kind(path),
         "raw_integrity":"NOT_CHECKED","g2_official_verified":False}
    try:
        data=call(lambda:api.files().get_media(fileId=row["destination_id"]))
        if not data or len(data)>MAX_FILE:return {**res,"status":"RAW_EMPTY_OR_LIMIT"}
        if sha(data)!=row["source_sha256"]:return {**res,"status":"RAW_SHA_MISMATCH","raw_integrity":"HOLD"}
        native=evaluate_native(data,path,source,res["era"])
        return {**res,"status":native["status"],"raw_integrity":"PASS",
                "format_candidate":bool(native.get("candidate")),"observed":native}
    except Exception as err:
        return {**res,"status":"READ_OR_PARSE_HOLD","error_type":type(err).__name__}
def sample(source):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,source)
    assert_cohort(rows,source)
    representatives,buckets=ordered(rows,source)
    cases=[audit(r,source,api,call) for r in representatives[:N]]
    counts=dict(collections.Counter(c["status"] for c in cases))
    summary={"source":source,"sampled":len(cases),
             "format_candidates":sum(bool(c.get("format_candidate")) for c in cases),
             "holds":sum(not c.get("format_candidate") for c in cases),
             "available_era_format_groups":len(buckets),"status_counts":counts,
             "all_sampled_structural_candidate":bool(cases) and all(c.get("format_candidate") for c in cases),
             "official_g2_pass":0}
    report={"schema":SCHEMA,"source":source,"run":RUN,
            "parser_registry_version":REGISTRY_VERSION,
            "created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "summary":summary,"sample_records":cases,
            "note":"SAMPLE ONLY. No official publication/lineage attestation; no Bronze writes, no Silver/Gold."}
    name="v097_SEVEN_FORMAT_SMOKE_"+source+"_"+RUN+".json"
    rid=put_once(api,quality,name,report)
    upsert(api,control,"v097_SEVEN_FORMAT_SMOKE_"+source+"_LATEST.json",
           {"schema":SCHEMA,"source":source,"run":RUN,"report_id":rid,"summary":summary})
    print("SEVEN_SOURCE_SMOKE="+canonical({**summary,"report_id":rid}),flush=True)
def selftest():
    assert len(SOURCES)==7
    assert set(SOURCES)==set(OFFICIAL_VERSIONS)
    from scripts.v097_two_source_pilot_g2 import csv_evidence
    c=csv_evidence("日期,契約,到期月份(週別),成交量\n2026-11-18,TX,202612,3\n".encode(),
                   "t.csv","TAIFEX","TAIFEX_DAY_AND_AFTER_HOURS")
    assert c["candidate"] and c["row_count"]==1
    assert all(s in OFFICIAL_VERSIONS for s in SOURCES)
    print("SEVEN_SOURCE_TEMPLATE_SMOKE_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="sample" and sys.argv[2] in SOURCES:sample(sys.argv[2])
    else:raise SystemExit("usage: selftest | sample SOURCE")
