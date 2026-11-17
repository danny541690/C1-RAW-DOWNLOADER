#!/usr/bin/env python3
"""G2/G3 source-native typed contract evidence. Incremental, conservative, QA-only.
A sample validation is NOT a full-file schema attestation or Silver Schema Ready.
Never modifies Bronze or materializes Silver/Gold.
"""
import collections,csv,hashlib,io,json,os,re,sys,zipfile
from datetime import datetime,timezone
from scripts.v097_v3_preflight import SOURCES,read_baseline,assert_cohort,load_evidence,source_api,canonical
from scripts.v097_v3_contract_registry import infer,REGISTRY_VERSION,CONTRACTS,normalize
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_g2g3_native_headers import HEADER_PREFIX,header_for,sha
from scripts.v097_g2g3_full_native_validation import full_scan,MAX_BYTES as FULL_SCAN_MAX
VERSION="v097_g2g3_typed_contract_audit_r1"
FULL_VALIDATOR_VERSION="v097_g2g3_full_native_validation_r1"
RUN=os.environ.get("GITHUB_RUN_ID","manual")
BATCH=max(1,min(35,int(os.environ.get("G2G3_TYPED_BATCH","15"))))
CHECKPOINT="v097_G2G3_TYPED_AUDIT_CK_"
LIMIT=65*1024*1024
DATE_KEYS={"date","period"}
CODE_KEYS={"code","contract","expiration"}
NUMERIC_KEYS={"open","high","low","close","volume","amount","revenue","holders","shares","percent","value"}
def evidence_fp(header):
    # Parser and contract revisions invalidate only affected source-ID records.
    item={"sha":header.get("sha"),"full_validator_version":FULL_VALIDATOR_VERSION,
      "parser_revision":header.get("parser_revision"),
      "registry":REGISTRY_VERSION,
      "headers":[{"path":e.get("path"),"sha":e.get("sha"),
                  "header":e.get("header"),"status":e.get("status")}
                 for e in header.get("evidence",[])]}
    return hashlib.sha256(canonical(item).encode("utf-8")).hexdigest()
def typecheck(key,val):
    if val is None or str(val).strip() in ("","--","-","N/A","NA","null","None"):
        return "NULL_NEEDS_NULL_POLICY"
    s=str(val).strip().replace(",","")
    if key in DATE_KEYS:
        return "DATE_SHAPE" if re.fullmatch(r"(?:\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?|\d{5,7}|\d{2,3}[/\-]\d{1,2}[/\-]\d{1,2})",s) else "DATE_PARSE_PENDING"
    if key in CODE_KEYS:return "CODE_SHAPE" if len(s)<=32 else "CODE_OVERLEN"
    if key in NUMERIC_KEYS:
        try:
            x=float(s)
            return "NUMBER_SHAPE" if x==x and abs(x)<1e30 else "NONFINITE_NUMBER"
        except ValueError:return "NUMBER_PARSE_FAILED"
    return "UNKNOWN_TYPE_RULE"
def csv_rows(blob):
    for enc in ("utf-8-sig","cp950","big5"):
        try:
            rows=list(csv.reader(io.StringIO(blob[:512*1024].decode(enc))))
            return [r for r in rows if len(r)>1][:70],enc
        except (UnicodeError,csv.Error):continue
    return [],"UNKNOWN"
def json_rows(blob):
    try:
        p=json.loads(blob.decode("utf-8-sig"))
        if isinstance(p,dict):
            for k in ("data","records","result"):
                if isinstance(p.get(k),list):p=p[k];break
        if isinstance(p,list):return [r for r in p[:50] if isinstance(r,dict)]
    except (ValueError,UnicodeError):pass
    return []
def validate_member(blob,path,header,src,era,dataset_hint):
    c=infer(src,header,era,dataset_hint)
    status=c.get("status")
    result={"status":status,"dataset_candidate":c.get("dataset_candidate"),
      "era_registered":c.get("era_registered"),"missing":c.get("missing_required"),
      "typed_sampled_rows":0,"typed_failures":{},"g2_verified":False,"g3_verified":False,
      "release":False,"type_semantics_certified":False,"official_contract_attested":False,
      "contract_registry":REGISTRY_VERSION}
    if status!="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED":return result
    keys=c.get("observed_fields",{})
    low=path.lower()
    if low.endswith((".csv",".txt")):
        rows,enc=csv_rows(blob)
        if not rows:return {**result,"status":"CSV_ROWS_UNREADABLE"}
        hindex=next((i for i,row in enumerate(rows[:15]) if all(
            normalize(h) in {normalize(x) for x in row} for h in keys.values())),None)
        if hindex is None:return {**result,"status":"CSV_HEADER_NOT_REIDENTIFIED"}
        header_row=rows[hindex]
        colindex={k:next((i for i,x in enumerate(header_row) if normalize(x)==normalize(v)),None)
                  for k,v in keys.items()}
        checked=rows[hindex+1:hindex+41]
        if not checked:return {**result,"status":"NO_DATA_ROWS"}
        failures=collections.Counter()
        for row in checked:
            for field,col in colindex.items():
                val=row[col] if col is not None and col<len(row) else None
                verdict=typecheck(field,val)
                if verdict not in ("DATE_SHAPE","CODE_SHAPE","NUMBER_SHAPE"):failures[field+":"+verdict]+=1
        result.update({"typed_sampled_rows":len(checked),"typed_failures":dict(failures),
          "status":"TYPED_SAMPLE_PASS_NOT_FULL_VALIDATION" if not failures else "TYPED_SAMPLE_EXCEPTION"})
    elif low.endswith(".json"):
        rows=json_rows(blob)
        if not rows:return {**result,"status":"JSON_ROWS_UNREADABLE"}
        failures=collections.Counter()
        for row in rows:
            for field,actual in keys.items():
                val=next((v for k,v in row.items() if normalize(k)==normalize(actual)),None)
                verdict=typecheck(field,val)
                if verdict not in ("DATE_SHAPE","CODE_SHAPE","NUMBER_SHAPE"):failures[field+":"+verdict]+=1
        result.update({"typed_sampled_rows":len(rows),"typed_failures":dict(failures),
          "status":"TYPED_SAMPLE_PASS_NOT_FULL_VALIDATION" if not failures else "TYPED_SAMPLE_EXCEPTION"})
    else:
        result["status"]="NATIVE_ROW_VALIDATOR_PENDING"
    return result
def source(src):
    if src not in SOURCES:raise ValueError("BAD_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
    hf=match(api,control,HEADER_PREFIX+src+".json")
    headers=load_json(api,hf["id"]).get("done",{}) if hf else {}
    idx={r["source_id"]:r for r in rows}
    if set(headers)-set(idx):raise RuntimeError("HEADER_ORPHANS")
    fn=CHECKPOINT+src+".json";f=match(api,control,fn)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"done":{}}
    if ck.get("schema")!=VERSION:raise RuntimeError("TYPED_CHECKPOINT_VERSION")
    done=ck["done"];new={}
    for sid,head in headers.items():
        row=idx[sid]
        if head.get("sha")!=row["source_sha256"] or not head.get("evidence"):continue
        current_fp=evidence_fp(head)
        if sid in done and done[sid].get("sha")==row["source_sha256"] and done[sid].get("header_evidence_fp")==current_fp and done[sid].get("registry")==REGISTRY_VERSION and done[sid].get("status")!="READ_OR_PARSE_PENDING":continue
        if len(new)>=BATCH:break
        output={"source_id":sid,"sha":row["source_sha256"],"header_evidence_fp":current_fp,"source":src,
          "run":RUN,"registry":REGISTRY_VERSION,"status":"EVIDENCE_PENDING",
          "silver_materialized":False,"gold_materialized":False,"g2_verified":False,"g3_verified":False}
        try:
            b=call(lambda:api.files().get_media(fileId=row["destination_id"]))
            if not b or len(b)>LIMIT:output["status"]="RAW_READ_OR_SIZE_HOLD"
            elif sha(b)!=row["source_sha256"]:output["status"]="ORIGINAL_SHA_MISMATCH"
            else:
                samples=[]
                if zipfile.is_zipfile(io.BytesIO(b)):
                    with zipfile.ZipFile(io.BytesIO(b)) as z:
                        for e in head["evidence"]:
                            if not e.get("header") or e.get("path") not in z.namelist():continue
                            info=z.getinfo(e["path"])
                            if info.file_size>8*1024*1024:continue
                            blob=z.read(info)
                            if e.get("sha")!=sha(blob):continue
                            samples.append({"member":e["path"],"type_evidence":validate_member(blob,e["path"],e["header"],src,head.get("historical_era"),None),
                              "full_native_shape":full_scan(blob,e["path"],src,head.get("historical_era"),e["header"])})
                else:
                    for e in head["evidence"]:
                        if e.get("header"):
                            samples.append({"member":e.get("path"),"type_evidence":validate_member(b,e.get("path",""),e["header"],src,head.get("historical_era"),None),
                                "full_native_shape":full_scan(b,e.get("path",""),src,head.get("historical_era"),e["header"])})
                output["status"]="TYPED_EVIDENCE_RECORDED" if samples else "TYPED_EVIDENCE_UNAVAILABLE"
                output["members"]=samples
        except Exception as e:
            output["status"]="READ_OR_PARSE_PENDING";output["error_type"]=type(e).__name__
        new[sid]=output
    if new:
        fid=put_once(api,quality,"v097_G2G3_TYPED_DELTA_"+src+"_"+RUN+".json",
          {"schema":VERSION,"source":src,"run":RUN,"records":new})
        done.update(new);ck["done"]=done;ck["last_run"]=RUN
        ck["history"]=(ck.get("history",[])+[{"run":RUN,"delta_id":fid,"n":len(new)}])[-100:]
        upsert(api,control,fn,ck)
        rf=match(api,control,fn)
        if not rf or len(load_json(api,rf["id"]).get("done",{}))!=len(done):
            raise RuntimeError("TYPED_READBACK_MISMATCH")
    out={"source":src,"run":RUN,"new":len(new),"checked":len(done),
         "full_native_shape_candidate_members":sum(1 for rec in done.values() for m in rec.get("members",[])
              if m.get("full_native_shape",{}).get("status")=="FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED"),
         "full_native_shape_exception_members":sum(1 for rec in done.values() for m in rec.get("members",[])
              if m.get("full_native_shape",{}).get("status")=="FULL_NATIVE_SHAPE_EXCEPTIONS"),
         "typed_sample_pass_members":sum(1 for rec in done.values() for m in rec.get("members",[])
              if m["type_evidence"]["status"]=="TYPED_SAMPLE_PASS_NOT_FULL_VALIDATION"),
         "statuses":dict(collections.Counter(v["status"] for v in done.values())),
         "schema_ready":0}
    print("G2G3_TYPED_PROGRESS="+canonical(out),flush=True)
def selftest():
    era=OFFICIAL_VERSIONS["FinMind"]["periods"][0]["id"]
    header=["date","stock_id","open","max","min","close","Trading_Volume","Trading_money"]
    csvfile=(",".join(header)+"\n2026-11-17,2330,100,105,98,103,1000,100000\n").encode()
    a=validate_member(csvfile,"test.csv",header,"FinMind",era,None)
    assert a["typed_sampled_rows"]==1
    assert a["status"]=="TYPED_SAMPLE_PASS_NOT_FULL_VALIDATION"
    assert a["g3_verified"] is False and a["release"] is False
    bad=validate_member(csvfile.replace(b",103,",b",bad,"),"test.csv",header,"FinMind",era,None)
    assert bad["status"]=="TYPED_SAMPLE_EXCEPTION"
    assert typecheck("value","--")=="NULL_NEEDS_NULL_POLICY"
    h={"sha":"a"*64,"parser_revision":"r1","evidence":[{"path":"a.csv","sha":"b"*64,"header":["date"]}]}
    assert evidence_fp(h)!=evidence_fp({**h,"parser_revision":"r2"})
    assert evidence_fp(h)!=evidence_fp({**h,"evidence":[{"path":"a.csv","sha":"b"*64,"header":["date","stock_id"]}]})
    assert evidence_fp(h)!=evidence_fp({**h,"parser_revision":"changed"})
    print("G2G3_TYPED_AUDIT_SAFETY_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source":source(sys.argv[2])
    else:raise SystemExit("selftest|source SOURCE")
