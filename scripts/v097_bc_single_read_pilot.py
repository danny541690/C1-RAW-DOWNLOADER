#!/usr/bin/env python3
"""v0.97 B+C merged read-only pilot: single ZIP open & each member read once.
Produces parallel B/C evidence; cannot write checkpoints or promote Silver Ready.
Compares key invariants with legacy independent B/C in selftest.
"""
import io,json,zipfile,re
from collections import Counter
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import digest
from scripts.v097_b_format_forensics import fingerprint,manifest_linkage,safe_name,era,OFFICIAL,PROVIDER
from scripts.v097_c_manifest_numeric import inspect_member,DOMAIN
MAX_ZIP=50*1024*1024
MAX_MEMBER=20*1024*1024
MAX_UNPACKED=100*1024*1024
MAX_MEMBERS=400
VERSION="bc-single-read-pilot-1"

def joint_audit(source,row,blob):
 """Return (b_record,c_record); no side effects or external provenance claims."""
 base={"source_id":row["source_id"],"source_sha256":row["sha"],
       "silver_ready_promoted":False}
 b={**base,"era":era(source,str(row["year"])+"-"+str(row["month"])),
    "official_reference":OFFICIAL[source],"third_party_reference":PROVIDER,
    "official_bytes_retrieved_independently":False}
 c={**base,"audit_version":VERSION,"official_origin_retrieved":False,
    "third_party_values_compared":False,"publication_time_verified":False}
 if digest(blob)!=row["sha"]:
  return {**b,"status":"HOLD_SOURCE_DEST_SHA_MISMATCH"},{**c,"status":"HOLD_SHA_MISMATCH"}
 if len(blob)>MAX_ZIP or not zipfile.is_zipfile(io.BytesIO(blob)):
  return {**b,"status":"HOLD_BOUNDS_OR_NOT_ZIP"},{**c,"status":"HOLD_NOT_ZIP"}
 try:
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   info=[m for m in z.infolist() if not m.is_dir()]
   if len(info)>MAX_MEMBERS or len({m.filename for m in info})!=len(info):
    return {**b,"status":"HOLD_ARCHIVE_MEMBER_DUPLICATE_OR_LIMIT"},{**c,"status":"HOLD_ARCHIVE_MEMBER_DUPLICATE_OR_LIMIT"}
   all_fingerprints=[];parsed=[];bytes_total=0;manifest_docs=[]
   for m in info:
    if not safe_name(m.filename):
     return {**b,"status":"HOLD_UNSAFE_MEMBER"},{**c,"status":"HOLD_UNSAFE_MEMBER"}
    if m.flag_bits&1 or m.file_size>MAX_MEMBER:
     return {**b,"status":"HOLD_ARCHIVE_MEMBER_SECURITY_OR_SIZE"},{**c,"status":"HOLD_ARCHIVE_MEMBER_SECURITY_OR_SIZE"}
    bytes_total+=m.file_size
    if bytes_total>MAX_UNPACKED:
     return {**b,"status":"HOLD_ZIP_EXPANSION_LIMIT"},{**c,"status":"HOLD_ZIP_EXPANSION_LIMIT"}
    data=z.read(m)
    if len(data)!=m.file_size:
     return {**b,"status":"HOLD_ZIP_MEMBER_SIZE"},{**c,"status":"HOLD_ZIP_MEMBER_SIZE"}
    all_fingerprints.append(fingerprint(m.filename,data))
    if m.filename.rsplit("/",1)[-1].lower()=="manifest.json":
     try:
      obj=json.loads(data.decode("utf-8-sig"))
      if isinstance(obj,dict):manifest_docs.append(obj)
     except (UnicodeError,ValueError):pass
    else:
     parsed.append({"member":m.filename[:160],"sha256":digest(data),**inspect_member(data)})
   linkage=manifest_linkage(z,all_fingerprints)
  f_counts=Counter(x["signature"] for x in all_fingerprints)
  finger_counts=Counter(x["dataset_fingerprint"] for x in all_fingerprints)
  b.update(status="B_CONTENT_FINGERPRINTED_SOURCE_PROOF_PENDING",
    member_count=len(all_fingerprints),members=all_fingerprints,
    manifest_linkage=linkage,formats=dict(f_counts),dataset_fingerprints=dict(finger_counts))
  src_hosts=Counter();src_claims=0
  for doc in manifest_docs:
   for unit in doc.get("units",[])[:15000]:
    if not isinstance(unit,dict):continue
    url=next((unit.get(k) for k in ("source_url","official_url","url","endpoint") if isinstance(unit.get(k),str)),None)
    if url:
     host=(urlparse(url).hostname or "").lower()
     src_hosts[host[:80]]+=1
     if host in DOMAIN[source]:src_claims+=1
  categories=Counter(k for p in parsed for k,n in p.get("datasets",{}).items() for _ in range(n))
  invalid=sum(p.get("invalid_numeric_cells",0) for p in parsed)
  widths=sum(p.get("row_width_conflicts",0) for p in parsed)
  evidence_conflict=sum(p.get("hash_or_shape_conflicts",0)+p.get("missing_member_references",0) for p in linkage)
  if not linkage:status="HOLD_NO_MANIFEST_PROOF"
  elif evidence_conflict:status="HOLD_MANIFEST_LINKAGE_CONFLICT"
  elif invalid or widths:status="HOLD_NUMERIC_OR_WIDTH_CONFLICT"
  elif not categories or set(categories)=={"UNRESOLVED_SCHEMA"}:status="HOLD_DATASET_IDENTITY_UNRESOLVED"
  else:status="C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"
  c.update(status=status,table_datasets=dict(categories),manifest_linkage=linkage,
    numeric_cells_checked=sum(p.get("numeric_cells_checked",0) for p in parsed),
    invalid_numeric_cells=invalid,row_width_conflicts=widths,
    source_url_hosts_seen=dict(src_hosts),official_host_claims_in_manifest=src_claims,
    members=parsed[:60])
  return b,c
 except (ValueError,zipfile.BadZipFile,RuntimeError,UnicodeError,MemoryError) as e:
  return {**b,"status":"HOLD_ZIP_CONTENT_ERROR","error_type":type(e).__name__},{**c,"status":"HOLD_ZIP_CONTENT_ERROR","error_type":type(e).__name__}

def selftest():
 from scripts.v097_b_format_forensics import audit as old_b
 from scripts.v097_c_manifest_numeric import audit as old_c
 import hashlib
 for source in ("TWSE","TPEx"):
  for schema in ("quotes","capitalization","bad","broken_manifest"):
   if schema=="capitalization":
    fields=["排名","股票代號","收盤價","市值(佰萬元)"];rowdata=["1","2330","100","250000"]
   else:
    fields=["代號","收盤","開盤","最高","最低","成交股數","成交統計"]
    rowdata=["2330","not-a-number" if schema=="bad" else "100","99","101","98","10000","1.一般股票"]
   payload=json.dumps({"date":"20261116","tables":[{"fields":fields,"data":[rowdata]}]},ensure_ascii=False).encode()
   member="quote.raw";hashval=("0"*64 if schema=="broken_manifest" else digest(payload))
   manifest={"units":[{"file":member,"sha256":hashval,"url":"https://www."+("twse.com.tw" if source=="TWSE" else "tpex.org.tw")+"/data"}]}
   file=io.BytesIO()
   with zipfile.ZipFile(file,"w") as z:
    z.writestr(member,payload);z.writestr("manifest.json",json.dumps(manifest).encode())
   data=file.getvalue();row={"source_id":"synthetic","sha":digest(data),"year":"2026","month":"11","source_path":"2026/11/archive.zip"}
   b,c=joint_audit(source,row,data)
   ob,oc=old_b(source,row,data),old_c(source,row,data)
   for key in ("status","formats","dataset_fingerprints","member_count"):
    assert b.get(key)==ob.get(key),(source,schema,"B",key,b.get(key),ob.get(key))
   for key in ("status","table_datasets","numeric_cells_checked","invalid_numeric_cells","row_width_conflicts","official_host_claims_in_manifest"):
    assert c.get(key)==oc.get(key),(source,schema,"C",key,c.get(key),oc.get(key))
   assert not c["official_origin_retrieved"] and not c["silver_ready_promoted"]
 print("BC_SINGLE_READ_PILOT_CONTRACT_PASS scenarios=8")
if __name__=="__main__":selftest()
