"""Collect bounded real G2 native format/date candidate evidence per source.

The 70 samples are bytes-verified directly from v0.97 Bronze.
Native dataset/date are candidates until independently attested against
actual official original and dataset-era spec. No formal G2 registry writes.
"""
from __future__ import annotations
import collections,csv,hashlib,io,json,os,re,sys,zipfile
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_schema_gate_v21 import read_baseline,inspect
from scripts.v097_v3_preflight import assert_cohort
from scripts.v097_r3_gate_core import SOURCES,COHORT
from scripts.v097_bronze_first_pipeline import put_once
FOLDER="R3_G2_NATIVE_FORMAT_EVIDENCE_CANDIDATES"
MAX_BYTES=2*1024*1024
SCAN_RADIUS=45
TARGET=10

def candid(blob,path,src):
    result={"signature":"UNKNOWN","dataset_candidate":None,"native_header":[],
            "native_date_candidate":None,"date_verified":False,
            "official_dataset_era_attested":False,"native_layout_verified":False,
            "source_format_candidates_only":True}
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos=[i for i in z.infolist() if not i.is_dir()]
            result["signature"]="ZIP"
            result["zip_members"]=len(infos)
            result["zip_member_names_redacted"]=True
            expanded=sum(i.file_size for i in infos)
            result["zip_total_decompressed_bytes"]=expanded
            result["zip_crc_verified"]=z.testzip() is None if len(infos)<=100 and expanded<=16*1024*1024 else None
            result["zip_member_schema_attested"]=False
    else:
        try:
            profile=inspect(blob,path,src)
            result["signature"]=profile.get("signature") or profile.get("status","UNKNOWN")
            result["dataset_candidate"]=profile.get("dataset_candidate") or profile.get("dataset")
            rawkeys=profile.get("header") or profile.get("keys") or []
            if isinstance(rawkeys,list):
                result["native_header"]=[str(v)[:96] for v in rawkeys[:35]]
        except Exception:
            result["signature"]="FORMAT_PROFILE_EXCEPTION"
    if not zipfile.is_zipfile(io.BytesIO(blob)) and isinstance(blob,bytes) and blob.lstrip()[:1] in (b"{",b"["):
        try:
            obj=json.loads(blob.decode("utf-8-sig"))
            if isinstance(obj,dict):
                result["dataset_candidate"]=result["dataset_candidate"] or obj.get("dataset")
                possible=[str(obj[k]) for k in ("date","Date","資料日期","交易日期","month","年月") if k in obj]
                if possible:result["native_date_candidate"]=possible[0][:24]
                if isinstance(obj.get("data"),list) and obj["data"] and isinstance(obj["data"][0],dict):
                    result["native_header"]=[str(v)[:96] for v in list(obj["data"][0])[:35]]
        except (UnicodeError,ValueError,TypeError):pass
    elif b"\x00" not in blob[:256]:
        for enc in ("utf-8-sig","cp950","big5"):
            try:
                txt=blob.decode(enc)
                row=next(csv.reader(io.StringIO(txt)),None)
                if row and len(row)>1:result["native_header"]=[str(x)[:96] for x in row[:35]]
                break
            except (UnicodeError,csv.Error):pass
    # filename-derived YYYYMM: useful for LOOKUP but never official date evidence.
    m=re.search(r"(20\d{2})[-_/]?(0[1-9]|1[0-2])",path)
    result["path_month_candidate"]=m.group(1)+"-"+m.group(2) if m else None
    result["path_month_is_attested"]=False
    return result

def run():
    api,control,quality,match,load_json,_,_,call=source_api()
    root=match(api,quality,FOLDER)
    if not root:
        root=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
             "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
    if root["mimeType"]!="application/vnd.google-apps.folder":raise RuntimeError("NOT_FOLDER")
    run_id=os.environ.get("GITHUB_RUN_ID","manual")
    summary={"schema":"R3_G2_REAL_NATIVE_CANDIDATES_V1","run":run_id,"source":[],
             "official_approved":0,"native_certified":0,"g2_released":0,"no_bronze_write":True}
    total=0
    for src in SOURCES:
        records=read_baseline(api,quality,match,load_json,src);assert_cohort(records,src)
        total+=len(records)
        picks=[];seen=set();counts=collections.Counter()
        for i in range(TARGET):
            loc=int((i+.5)*len(records)/TARGET)
            for offset in range(SCAN_RADIUS):
                idx=min(len(records)-1,loc+offset)
                if idx in seen:continue
                seen.add(idx);row=records[idx]
                try:
                    meta=call(lambda:api.files().get(fileId=row["destination_id"],fields="id,size,mimeType"))
                    if int(meta.get("size") or MAX_BYTES+1)>MAX_BYTES:continue
                    blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
                    if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:
                        counts["SHA_MISMATCH"]+=1;break
                    detail=candid(blob,str(row.get("source_path") or ""),src)
                    detail.update({"source_id":row["source_id"],"source_sha256":row["source_sha256"]})
                    picks.append(detail);counts["VERIFIED_BYTES"]+=1
                    counts["SIGNATURE_"+detail["signature"][:48]]+=1
                    if detail["native_header"]:counts["HAS_HEADER_CANDIDATE"]+=1
                    if detail["native_date_candidate"]:counts["HAS_NATIVE_DATE_CANDIDATE"]+=1
                    if detail["path_month_candidate"]:counts["HAS_PATH_MONTH_CANDIDATE"]+=1
                    break
                except Exception as e:
                    counts["READ_ERROR_"+type(e).__name__]+=1;break
        obj={"schema":"R3_G2_NATIVE_CANDIDATE_SHARD_V1","source":src,"run":run_id,
             "cohort":len(records),"counts":dict(counts),"records":picks,
             "note":"Not official G2 approval; these only help select precise official native template."}
        name="r3_g2_native_candidates_"+src+"_run_"+run_id+".json"
        fid=put_once(api,root["id"],name,obj)
        if load_json(api,fid)!=obj:raise RuntimeError("DRIVE_NATIVE_CANDIDATE_READBACK_FAILED_"+src)
        s={"source":src,"source_cohort":len(records),"samples":len(picks),"counts":dict(counts),
           "receipt":name,"readback":True}
        summary["source"].append(s)
        print("R3_G2_NATIVE_CANDIDATE_SOURCE="+json.dumps(s,ensure_ascii=False,sort_keys=True),flush=True)
    if total!=COHORT:raise RuntimeError("FROZEN_COHORT_CHANGED")
    name="r3_g2_native_candidates_master_run_"+run_id+".json"
    mid=put_once(api,root["id"],name,summary)
    if load_json(api,mid)!=summary:raise RuntimeError("NATIVE_CANDIDATE_MASTER_MISMATCH")
    print("R3_G2_NATIVE_CANDIDATE_MASTER="+json.dumps({
       "run":run_id,"cohort":COHORT,"sample_count":sum(s["samples"] for s in summary["source"]),
       "official_approved":0,"sources":summary["source"],
       "master":name,"master_id":mid,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":
    if sys.argv[1:]!=["run"]:raise SystemExit("usage: run")
    run()
