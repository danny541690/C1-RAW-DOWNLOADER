#!/usr/bin/env python3
"""TDCC/TAIFEX read-only pilot then gated incremental native-format audit.
No G2 official attestation is minted here. Never touches Bronze or R1 G2 certificates.
"""
import collections,csv,hashlib,io,json,os,sys,zipfile
from datetime import datetime,timezone
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_g2g3_native_headers import header_for
from scripts.v097_g2g3_tdcc_native_html import inspect as inspect_tdcc
from scripts.v097_v3_contract_registry import infer
from scripts.v097_seven_historical_format_registry import period

VERSION="v097_two_source_pilot_v1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCES=("TDCC","TAIFEX")
PILOT_PER_SOURCE=12
BATCH=min(100,max(1,int(os.getenv("G2_TWO_SOURCE_BATCH","50"))))
MAX_FILE=16*1024*1024
REPORT_PREFIX="v097_TWO_SOURCE_PILOT_"
CK_PREFIX="v097_TWO_SOURCE_BATCH_CK_"
def sha(x):return hashlib.sha256(x).hexdigest()
def kind(path):
    p=(path or "").lower().split("?")[0]
    for ext in (".html",".htm",".csv",".txt",".jsonl",".json",".zip",".raw"):
        if p.endswith(ext):return ext
    return "OTHER"
def era(row,src):
    # Date is a candidate for selecting the correct historical parser,
    # NOT proof of a publication date or original official availability.
    from datetime import datetime
    import re
    tokens=[str(row.get("data_date") or ""),str(row.get("date") or ""),
            str(row.get("source_path") or "")]
    for token in tokens:
        for matched in re.findall(r"(?<!\\d)(20\\d{2})[-_/]?(0[1-9]|1[0-2])(?:[-_/]?([0-3]\\d))?(?!\\d)",token):
            y,m,_=matched
            try:return period(src,y+"-"+m)["id"]
            except (ValueError,KeyError,TypeError):continue
    return "ERA_UNKNOWN"
def ordered(rows,src):
    buckets={}
    for row in rows:
        key=era(row,src)+"|"+kind(row.get("source_path",""))
        buckets.setdefault(key,[]).append(row)
    for key in buckets:
        buckets[key].sort(key=lambda r:(str(r.get("data_date","")),str(r["source_id"])))
    # Representative early/middle/late files per available era and native extension
    keys=sorted(buckets,key=lambda x:(("PRE_PUBLIC" in x or "ERA_UNKNOWN" in x),
                                       0 if x.endswith((".csv",".html",".htm")) else 1,x))
    selected=[];seen=set()
    for key in keys:
        group=buckets[key]
        for pos in sorted(set((0,len(group)//2,len(group)-1))):
            row=group[pos]
            if row["source_id"] not in seen:
                selected.append(row);seen.add(row["source_id"])
    return selected, buckets
def csv_evidence(data,path,src,historical):
    for enc in ("utf-8-sig","cp950","big5"):
        try:
            parsed=list(csv.reader(io.StringIO(data.decode(enc))))
            break
        except (UnicodeDecodeError,csv.Error):continue
    else:return {"status":"ENCODING_HOLD","candidate":False}
    active=[r for r in parsed if any(str(v).strip() for v in r)]
    candidates=[]
    for i,row in enumerate(active[:20]):
        if len(row)<3:continue
        clean=row[:]
        while clean and not clean[-1].strip():clean.pop()
        proof=infer(src,clean,historical)
        score=len(proof.get("observed_fields",{}))
        candidates.append((score,i,clean,proof))
    if not candidates:return {"status":"CSV_HEADER_NOT_FOUND","candidate":False}
    score,i,h,proof=max(candidates,key=lambda z:(z[0],-z[1]))
    data_rows=active[i+1:]
    widths=collections.Counter(len(r) for r in data_rows)
    extra_blank=sum(bool(len(r)>len(h) and all(not x.strip() for x in r[len(h):])) for r in data_rows)
    extra_nonblank=sum(bool(len(r)>len(h) and any(x.strip() for x in r[len(h):])) for r in data_rows)
    candidate=proof.get("status")=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED" and len(data_rows)>0 and extra_nonblank==0
    return {"status":"STRUCTURE_CANDIDATE" if candidate else "CSV_MAPPING_HOLD",
            "candidate":candidate,"encoding":enc,"header":h[:40],"first_rows":data_rows[:2],
            "row_count":len(data_rows),"widths":dict(widths),"trailing_blank_rows":extra_blank,
            "trailing_nonblank_rows":extra_nonblank,"contract_candidate":proof}
def inspect_blob(raw,path,src,historical):
    ext=kind(path)
    if ext in (".html",".htm") and src=="TDCC":
        p=inspect_tdcc(raw,path)
        head=p.get("observed_header",[])
        match=infer(src,head,historical,metadata=p.get("metadata"))
        candidate=(p["status"]=="TDCC_FULL_NATIVE_LAYOUT_CANDIDATE_UNCERTIFIED" and
                   match.get("status")=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED")
        return {"status":"STRUCTURE_CANDIDATE" if candidate else "TDCC_LAYOUT_HOLD",
                "candidate":candidate,"native":p,"contract_candidate":match}
    if ext in (".csv",".txt"):
        return csv_evidence(raw,path,src,historical)
    if ext==".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            files=[a for a in z.infolist() if not a.is_dir()]
            if len(files)>1000 or sum(a.file_size for a in files)>64*1024*1024:
                return {"status":"ZIP_RESOURCE_LIMIT","candidate":False}
            members=[]
            for info in files[:20]:
                if info.file_size>MAX_FILE or ".." in info.filename.replace("\\","/").split("/"):
                    return {"status":"ZIP_MEMBER_UNSAFE_OR_TOO_LARGE","candidate":False}
                child=z.read(info)
                if kind(info.filename) in (".csv",".txt"):
                    p=csv_evidence(child,info.filename,src,historical)
                elif src=="TDCC" and kind(info.filename) in (".htm",".html"):
                    p=inspect_blob(child,info.filename,src,historical)
                else:
                    p={"status":"MEMBER_DATASET_MAPPING_PENDING","candidate":False}
                members.append({"name":info.filename,"sha":sha(child),"result":p})
            ok=bool(members) and len(members)==len(files) and all(m["result"]["candidate"] for m in members)
            return {"status":"STRUCTURE_CANDIDATE" if ok else "ZIP_MEMBER_MAPPING_HOLD",
                    "candidate":ok,"members":members,"total_members":len(files)}
    p=header_for(raw,path,src)
    return {"status":"NON_CSV_NATIVE_MAPPING_PENDING","candidate":False,"header_evidence":p}
def audit(row,src,api,call):
    base={"source_id":row["source_id"],"source":src,"sha":row["source_sha256"],
          "path":row.get("source_path"),"era":era(row,src),
          "raw_integrity":"NOT_CHECKED","official_attested":False,"g2_pass":False}
    try:
        blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
        if not blob or len(blob)>MAX_FILE:return {**base,"status":"EMPTY_OR_SIZE_HOLD"}
        if sha(blob)!=row["source_sha256"]:
            return {**base,"status":"SHA_MISMATCH","raw_integrity":"HOLD"}
        proof=inspect_blob(blob,row.get("source_path",""),src,base["era"])
        return {**base,"raw_integrity":"PASS","status":proof["status"],
                "format_candidate":bool(proof["candidate"]),"evidence":proof}
    except Exception as ex:
        return {**base,"status":"READ_OR_PARSE_HOLD","error_type":type(ex).__name__}
def persist(api,control,quality,match,put_once,upsert,src,mode,report):
    name=REPORT_PREFIX+src+"_"+mode+"_"+RUN+".json"
    rid=put_once(api,quality,name,report)
    index={"schema":VERSION,"run":RUN,"source":src,"mode":mode,"report_id":rid,
           "summary":report["summary"],"at":datetime.now(timezone.utc).isoformat()}
    upsert(api,control,REPORT_PREFIX+src+"_"+mode+"_LATEST.json",index)
    return rid
def pilot(src):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
    select,buckets=ordered(rows,src)
    # Preserve coverage of different eras/extensions before expanding.
    cases=[audit(row,src,api,call) for row in select[:PILOT_PER_SOURCE]]
    passed=[c for c in cases if c.get("format_candidate")]
    reasons=dict(collections.Counter(c["status"] for c in cases))
    # Approve only individual era+format buckets with >=2 clean examples.
    # Unseen or mixed-format buckets NEVER enter batch even if other samples pass.
    group_cases=collections.defaultdict(list)
    for c in cases:
        key=c["era"]+"|"+kind(c.get("path",""))
        group_cases[key].append(c)
    approved=sorted(k for k,v in group_cases.items()
                    if len(v)>=2 and all(x.get("format_candidate") for x in v))
    allow_bulk=bool(approved)
    summary={"sampled":len(cases),"candidate":len(passed),"hold":len(cases)-len(passed),
             "status_counts":reasons,"buckets_available":len(buckets),
             "approved_era_format_buckets":approved,
             "allow_incremental_format_batch":allow_bulk,
             "formal_g2_pass":0}
    report={"schema":VERSION,"source":src,"mode":"PILOT","run":RUN,
            "summary":summary,"cases":cases,
            "policy":"FORMAT_ONLY_NOT_OFFICIAL_G2; Bronze unchanged"}
    rid=persist(api,control,quality,match,put_once,upsert,src,"PILOT",report)
    print("TWO_SOURCE_PILOT="+canonical({**summary,"source":src,"report_id":rid}),flush=True)
    return allow_bulk
def batch(src):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    index=match(api,control,REPORT_PREFIX+src+"_PILOT_LATEST.json")
    if not index:raise RuntimeError("PILOT_REQUIRED")
    pilot_index=load_json(api,index["id"])
    if pilot_index.get("schema")!=VERSION or not pilot_index.get("summary",{}).get("allow_incremental_format_batch"):
        raise RuntimeError("PILOT_NOT_CLEAR_NO_BATCH")
    approved=set(pilot_index["summary"].get("approved_era_format_buckets",[]))
    if not approved:raise RuntimeError("NO_APPROVED_ERA_FORMAT_BUCKET")
    rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
    eligible=[r for r in rows if era(r,src)+"|"+kind(r.get("source_path","")) in approved]
    ck_name=CK_PREFIX+src+".json"
    f=match(api,control,ck_name)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"done":{}}
    if ck.get("schema")!=VERSION:raise RuntimeError("CHECKPOINT_VERSION_CONFLICT")
    done=ck["done"];new={}
    for row in eligible:
        sid=row["source_id"]
        if sid in done and done[sid].get("sha")==row["source_sha256"]:continue
        new[sid]=audit(row,src,api,call)
        if len(new)>=BATCH:break
    if new:
        rid=put_once(api,quality,"v097_TWO_SOURCE_BATCH_DELTA_"+src+"_"+RUN+".json",
                     {"schema":VERSION,"source":src,"run":RUN,"records":new})
        done.update(new)
        ck.update({"done":done,"run":RUN,"delta_id":rid})
        upsert(api,control,ck_name,ck)
        back=match(api,control,ck_name)
        if not back or len(load_json(api,back["id"]).get("done",{}))!=len(done):
            raise RuntimeError("BATCH_CHECKPOINT_READBACK_FAILED")
    summary={"batch_new":len(new),"checked_total":len(done),"eligible_total":len(eligible),
             "remaining_eligible":sum(r["source_id"] not in done for r in eligible),
             "excluded_unapproved_buckets":len(rows)-len(eligible),
             "approved_era_format_buckets":sorted(approved),
             "statuses":dict(collections.Counter(x["status"] for x in done.values())),
             "formal_g2_pass":0}
    report={"schema":VERSION,"source":src,"mode":"BATCH","run":RUN,
            "summary":summary,"new":new,"policy":"FORMAT_CANDIDATE_ONLY_NO_G2_CERTIFICATE"}
    rid=persist(api,control,quality,match,put_once,upsert,src,"BATCH",report)
    print("TWO_SOURCE_BATCH="+canonical({**summary,"source":src,"report_id":rid}),flush=True)
def selftest():
    assert len(SOURCES)==2
    a=csv_evidence(b"\xef\xbb\xbf\xe6\x97\xa5\xe6\x9c\x9f,\xe5\xa5\x91\xe7\xb4\x84,\xe5\x88\xb0\xe6\x9c\x9f\xe6\x9c\x88\xe4\xbb\xbd(\xe9\x80\xb1\xe5\x88\xa5),\xe6\x88\x90\xe4\xba\xa4\xe9\x87\x8f\n2026-11-18,TX,202612,5,\n",
      "a.csv","TAIFEX","TAIFEX_DAY_AND_AFTER_HOURS")
    assert a["status"]=="STRUCTURE_CANDIDATE" and a["trailing_blank_rows"]==1
    b=csv_evidence(b"date,contract,expiration,volume\n2026-11-18,TX,202612,5,unexpected\n",
      "a.csv","TAIFEX","TAIFEX_DAY_AND_AFTER_HOURS")
    assert not b["candidate"]
    assert era({"source_path":"distribution_20251031_YHT8.html"},"TDCC")=="TDCC_WEEKLY_DISTRIBUTION"
    assert era({"source_path":"largeTraderFut_20160401.csv"},"TAIFEX")=="TAIFEX_DAY_SESSION_HISTORICAL"
    assert era({"source_path":"largeTraderFut_20240102.csv"},"TAIFEX")=="TAIFEX_DAY_AND_AFTER_HOURS"
    print("TWO_SOURCE_PILOT_SELFTEST_PASS")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ("pilot","batch") and sys.argv[2] in SOURCES:
        (pilot if sys.argv[1]=="pilot" else batch)(sys.argv[2])
    else:raise SystemExit("usage: selftest | pilot TDCC/TAIFEX | batch TDCC/TAIFEX")
