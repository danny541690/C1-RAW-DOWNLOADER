"""Targeted NDC/TAIFEX evidence for first real G2 certificate.
Read only real frozen Bronze and prior immutable 70-shard. Output bounded
structural truth, never certify absent original archive or official spec.
"""
import collections,hashlib,io,json,os,zipfile,csv,re
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import group_candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
FOLDER="R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED"
def run():
 api,control,quality,match,load,_,_,call=source_api()
 base=match(api,quality,"R3_G2_NATIVE_FORMAT_EVIDENCE_CANDIDATES")
 if not base:raise RuntimeError("PREVIOUS_70_EVIDENCE_MISSING")
 out={"schema":"R3_G2_FIRST_REAL_CERT_DISCOVERY_V1","run":RUN,"sources":[],
      "g2_certified":0,"official_approved":0,"no_bronze_writes":True}
 for src in ("NDC","TAIFEX"):
  rows=read_baseline(api,quality,match,load,src)
  index={r["source_id"]:r for r in rows}
  f=match(api,base["id"],f"r3_g2_native_candidates_{src}_run_44251892156.json")
  if not f:raise RuntimeError("PRIOR_EVIDENCE_SHARD_MISSING_"+src)
  olds=load(api,f["id"])["records"];assess=[]
  for old in olds:
   r=index.get(old["source_id"])
   if not r:raise RuntimeError("SOURCE_ID_ORPHAN")
   meta=call(lambda:api.files().get(fileId=r["destination_id"],fields="id,size,mimeType"))
   if int(meta.get("size") or 0)>2*1024*1024:continue
   blob=call(lambda:api.files().get_media(fileId=r["destination_id"]))
   if hashlib.sha256(blob).hexdigest()!=r["source_sha256"]:raise RuntimeError("BRONZE_BYTES_CHANGED")
   info={"source_id":r["source_id"],"source_sha256":r["source_sha256"],
         "native_format":"ZIP" if zipfile.is_zipfile(io.BytesIO(blob)) else ("JSON" if blob.lstrip().startswith((b"{",b"[")) else "CSV_OR_OTHER"),
         "official_document_sha_verified":False,"native_complete_verified":False}
   if src=="NDC":
    obj=json.loads(blob.decode("utf-8-sig"))
    info["keys"]=sorted(obj.keys()) if isinstance(obj,dict) else []
    info["source_archive"]=obj.get("source_archive") if isinstance(obj,dict) else None
    info["month"]=obj.get("month") if isinstance(obj,dict) else None
    info["source"]=obj.get("source") if isinstance(obj,dict) else None
    info["table_count"]=len(obj.get("tables",[])) if isinstance(obj.get("tables"),list) else 0
    if isinstance(obj.get("tables"),list) and obj["tables"]:
     sample=obj["tables"][0]
     info["sample_table_keys"]=sorted(sample) if isinstance(sample,dict) else []
     info["first_table_name"]=str(sample.get("table",""))[:90] if isinstance(sample,dict) else None
     info["first_cell_fields"]=[str(c.get("field"))[:90] for c in sample.get("cells",[])[:30] if isinstance(c,dict)] if isinstance(sample,dict) else []
   else:
    if info["native_format"]=="ZIP":
     z=zipfile.ZipFile(io.BytesIO(blob));members=z.infolist()
     info["members"]=len(members);info["expanded"]=sum(m.file_size for m in members)
     if len(members)<=25 and sum(m.file_size for m in members)<3*1024*1024:
      for zi in members[:1]:
       if zi.is_dir():continue
       raw=z.read(zi);info["first_member_sha256"]=hashlib.sha256(raw).hexdigest()
       for enc in ("utf-8-sig","cp950","big5"):
        try:
         head=next(csv.reader(io.StringIO(raw.decode(enc)),strict=True))
         info["first_member_header"]=head[:40];info["member_encoding"]=enc;break
        except (UnicodeError,csv.Error,StopIteration):pass
    else:
     for enc in ("utf-8-sig","cp950","big5"):
      try:info["header"]=next(csv.reader(io.StringIO(blob.decode(enc)),strict=True))[:45];break
      except (UnicodeError,csv.Error,StopIteration):pass
   assess.append(info)
  out["sources"].append({"source":src,"records":assess})
  print("R3_G2_FIRST_REAL_SOURCE="+json.dumps({"source":src,"samples":len(assess),
     "native_formats":dict(collections.Counter(v["native_format"] for v in assess)),
     "archive_refs":sum(bool(v.get("source_archive")) for v in assess),
     "sample_table_keys":assess[0].get("sample_table_keys") if assess else None,
     "first_header_candidate":(assess[0].get("header") or assess[0].get("first_member_header")) if assess else None
   },ensure_ascii=False,sort_keys=True),flush=True)
 fld=match(api,quality,FOLDER)
 if not fld:fld=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name="r3_g2_first_real_cert_discovery_run_"+RUN+".json"
 fid=put_once(api,fld["id"],name,out)
 if load(api,fid)!=out:raise RuntimeError("DRIVE_READBACK_FAILED")
 print("R3_G2_FIRST_REAL_MASTER="+json.dumps({"run":RUN,"receipt":name,"receipt_id":fid,"readback":True,
  "verified_records":sum(len(x["records"]) for x in out["sources"]),"formal_pass":0},sort_keys=True),flush=True)
if __name__=="__main__":run()
