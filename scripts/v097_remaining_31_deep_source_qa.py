#!/usr/bin/env python3
"""Deep v0.97 31 remaining dataset-level source validations.
Official TDCC 1-1/1-2 OpenAPI field schema, original SHA/MD5, archive ZIP
CRC+internal date/path/member counts, JSON row shape, TDCC HTML 15-16 level
totals and MOPS official metadata. Does not fabricate original source URL,
historical PIT, or promote unauthorized data into ordinary-stock Bronze.
"""
import os,re,io,json,hashlib,zipfile,requests
from collections import Counter
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call
from scripts.v097_tdcc_a3_a5_auto import html_identity,table_diagnostics
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("V097_31_LANE","0"))
def sha(b):return hashlib.sha256(b).hexdigest()
def select(api,q,lane):
 f=match(api,q,"v097_REMAINING_39_CONTENT_QA_43452888927.json")
 if not f:raise RuntimeError("39_FROZEN_QA_REPORT_MISSING")
 a=load_json(api,f["id"])
 if a.get("total")!=39:raise RuntimeError("FROZEN_39_COUNT_CONFLICT")
 pending=[x for x in a["rows"] if x["state"]!="OUT_OF_SCOPE_TICK_DATA_USER_EXCLUDED"]
 if len(pending)!=31:raise RuntimeError("EXPECTED_31_ACTIVE")
 return [x for x in pending if int(sha(x["fid"].encode())[:8],16)%6==lane]
def probe_schema():
 out={}
 for dataset in ("1-1","1-2"):
  url="https://openapi.tdcc.com.tw/v1/opendata/"+dataset
  info={"dataset":dataset,"official_url":url}
  try:
   r=requests.get(url,timeout=(12,65),headers={"User-Agent":"JARVIS-097-original-proof/1"})
   info["http"]=r.status_code
   if r.status_code!=200:raise ValueError("OFFICIAL_HTTP_NON200")
   if len(r.content)>65_000_000:raise ValueError("OFFICIAL_SIZE_LIMIT")
   data=r.json()
   if isinstance(data,list):
    info["row_count"]=len(data)
    info["schema_fields"]=list(data[0].keys()) if data and isinstance(data[0],dict) else []
   else:
    info["root_type"]=type(data).__name__
    info["schema_fields"]=list(data)[:35] if isinstance(data,dict) else []
   info["http_body_sha256"]=sha(r.content)
   info["state"]="OFFICIAL_SCHEMA_READABLE"
  except Exception as exc:info.update(state="OFFICIAL_SCHEMA_FETCH_HOLD",
       reason=type(exc).__name__+":"+str(exc)[:130])
  out[dataset]=info
 return out
def deep(api,item,schema):
 fid=item["fid"];result={"file_id":fid,"source":item["source"],"source_path":item.get("path"),
    "full_bronze_PIT_release":False,"original_093_unchanged":True}
 try:
  meta=call(lambda:api.files().get(fileId=fid,fields="name,size,md5Checksum"))
  size=int(meta.get("size") or 0)
  if not 0<size<=80_000_000:raise ValueError("ORIGINAL_OUT_OF_BOUNDED_DEEP_QA")
  raw=call(lambda:api.files().get_media(fileId=fid))
  if len(raw)!=size:raise ValueError("ORIGINAL_SIZE_NOT_MATCHED")
  digest=sha(raw)
  if item.get("sha256") and digest!=item["sha256"]:raise ValueError("ORIGINAL_SHA_CHANGED_FROM_PREVIOUS_QA")
  if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:raise ValueError("DRIVE_MD5_NOT_MATCHED")
  result.update(original_sha256=digest,bytes=size,original_name=meta["name"])
  if raw.startswith(b"PK\x03\x04"):
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    infos=z.infolist()
    if len(infos)>3000:raise ValueError("ARCHIVE_TOO_MANY_MEMBERS")
    if z.testzip() is not None:raise ValueError("ZIP_CRC_FAIL")
    total=sum(x.file_size for x in infos)
    if total>350_000_000:raise ValueError("ARCHIVE_EXCEEDS_UNCOMPRESSED_BOUND")
    members=[]
    for x in infos:
     path=x.filename.replace("\\","/")
     if path.startswith("/") or ".." in path.split("/") or x.is_dir():continue
     members.append(path)
    manifests=[x for x in members if "manifest" in x.lower() and x.endswith(".json")]
    checked=[]
    for mn in manifests[:3]:
     b=z.read(mn)
     if len(b)>8_000_000:raise ValueError("ZIP_MANIFEST_TOO_BIG")
     m=json.loads(b.decode("utf-8-sig"))
     checked.append({"name":mn,"root_type":type(m).__name__,
       "fields":list(m)[:30] if isinstance(m,dict) else [],
       "sha256":sha(b)})
    result.update(state="ARCHIVE_BYTES_CRC_PATH_AND_MANIFEST_QA_PASS_ORIGIN_PENDING",
       zip_members=len(infos),member_paths_sample=members[:9],uncompressed_bytes=total,
       manifest_proofs=checked)
  elif raw.lstrip().startswith((b"{",b"[")):
   obj=json.loads(raw.decode("utf-8-sig"))
   if not isinstance(obj,list) or len(obj)<100:raise ValueError("TDCC_DATASET_NOT_TABLE")
   if any(not isinstance(row,dict) for row in obj[:100]):raise ValueError("ROW_RECORD_SHAPE_INVALID")
   shape=list(obj[0].keys())
   for row in obj[:100]:
    if list(row.keys())!=shape:raise ValueError("TDCC_SCHEMA_KEYS_INCONSISTENT")
   dataset=meta["name"].split("_",1)[0]
   if dataset not in ("1-1","1-2"):raise ValueError("TDCC_UNKNOWN_OFFICIAL_DATASET")
   official=schema.get(dataset,{})
   result.update(state="TDCC_JSON_SOURCE_STRUCTURE_QA_PASS_EXTERNAL_HISTORY_PENDING",
       rows=len(obj),dataset=dataset,source_keys=shape,first_row=obj[0],
       official_schema_state=official.get("state"),official_current_schema=official.get("schema_fields"),
       official_current_sha256=official.get("http_body_sha256"))
   if official.get("state")=="OFFICIAL_SCHEMA_READABLE":
    result["official_key_intersection"]=sorted(set(shape)&set(official.get("schema_fields") or []))
  elif b"<html" in raw[:100000].lower():
   soup=BeautifulSoup(raw.decode("utf-8-sig",errors="replace"),"html.parser")
   if not soup.select("table"):raise ValueError("HTML_NO_TABLE")
   if item["source"]=="TDCC":
    code,dates,tables=html_identity(raw)
    qa=table_diagnostics(raw)
    result.update(html_security_code=code,selected_dates=dates,level_checks=qa,
      state="TDCC_HTML_TOTALS_QA_PASS_ID_DATE_SCOPE_PENDING" if qa.get("status")=="HTML_DISTRIBUTION_TOTALS_MATCH"
      else "TDCC_HTML_SEMANTICS_HOLD")
   elif item["source"]=="MOPS":
    text=soup.get_text(" ",strip=True)
    tags=["資產負債表","現金流量表","綜合損益表","營業收入"]
    known=[x for x in tags if x in text]
    result.update(html_tables=len(soup.select("table")),financial_labels=known,
       state="MOPS_HTML_QA_PASS_OFFICIAL_PUBLICATION_AND_ACCOUNTS_PENDING" if known
       else "MOPS_HTML_REPORT_IDENTITY_HOLD")
   else:result.update(state="HTML_NATIVE_FORMAT_PASS_SOURCE_SEMANTICS_PENDING",
       html_tables=len(soup.select("table")))
  else:raise ValueError("SOURCE_FORMAT_UNKNOWN")
 except Exception as exc:result.update(state="DEEP_QA_HOLD",
   reason=type(exc).__name__+":"+str(exc)[:180])
 return result
def main():
 api=service();_,c,q,_=common(api)
 rows=select(api,q,LANE)
 schema=probe_schema() if LANE==0 else {}
 # Provider schema lookup from official 1-1/1-2 is not historical provenance evidence.
 results=[deep(api,x,schema) for x in rows]
 out={"schema":"v097_31_deep_cross_format_1","run":RUN,
  "lane":LANE,"at":datetime.now(timezone.utc).isoformat(),
  "total":len(results),"by_state":dict(Counter(x["state"] for x in results)),
  "official_current_source_schema":schema,
  "ordinary_stock_bronze_promoted":0,"rows":results}
 put_once(api,q,"v097_31_DEEP_QA_"+RUN+"_L%02d.json"%LANE,out)
 print("DEEP_31_LANE="+json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
