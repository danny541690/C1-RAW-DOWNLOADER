#!/usr/bin/env python3
"""JARVIS v0.98 eight-source five-day evidence auditor: six official and Free lanes.
Read-only existing v0.98 Bronze (no redownload, no mutation); Free API anonymous.
One SOURCE per GitHub job. Five 2026/11/16..20 confirmed trading dates.
Data presence NOT inferred from folder existence. Only exact-dated content is evidence.
"""
import collections,csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error,zipfile
SOURCE=os.environ["JARVIS_AUDIT_SOURCE"]
OFFICIAL=("TWSE","TPEx","MOPS","NDC","TDCC","TAIFEX")
assert SOURCE in (*OFFICIAL,"FinMind_Free")
DAYS=["2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20"]
ROOT=pathlib.Path("eight_source_5days")/SOURCE;ROOT.mkdir(parents=True,exist_ok=True)
BROOT="13DY2S3TuC4KYr8JKiptzUeXG9xZyIzam";C1="1FzqFPBOKQH2mk324dZAtG7D5z_hGdwoa"
MIME="application/vnd.google-apps.folder"
RAW="https://raw.githubusercontent.com/danny541690/C1-RAW-DOWNLOADER/main/governance/v095/DATASET_CONTRACTS.csv"
FIN_DOC="https://raw.githubusercontent.com/FinMind/FinMind-MCP/master/knowledge/datasets.md"
def get(url,headers=None,limit=1800000):
 req=urllib.request.Request(url,headers={"User-Agent":"JARVIS-v098-eight-source-5days/1.0",**(headers or {})})
 with urllib.request.urlopen(req,timeout=38) as response:
  b=response.read(limit+1)
 if len(b)>limit:raise ValueError("RESPONSE_SIZE_LIMIT")
 return b
def auth():
 payload=urllib.parse.urlencode({"client_id":os.environ["GOOGLE_CLIENT_ID"],"client_secret":os.environ["GOOGLE_CLIENT_SECRET"],
 "refresh_token":os.environ["GOOGLE_REFRESH_TOKEN"],"grant_type":"refresh_token"}).encode()
 req=urllib.request.Request("https://oauth2.googleapis.com/token",data=payload,headers={"Content-Type":"application/x-www-form-urlencoded"})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)["access_token"]
def children(parent,token):
 rows=[];page=None
 for _ in range(7):
  params={"q":"'"+parent+"' in parents and trashed = false","pageSize":1000,
   "fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum)"}
  if page:params["pageToken"]=page
  url="https://www.googleapis.com/drive/v3/files?"+urllib.parse.urlencode(params)
  obj=json.loads(get(url,{"Authorization":"Bearer "+token},limit=1600000))
  rows+=obj.get("files",[]);page=obj.get("nextPageToken")
  if not page:return rows,True
 return rows,False
def find_named(folder,name,token):
 xs,_=children(folder,token)
 vals=[x for x in xs if x["name"]==name and x["mimeType"]==MIME]
 if len(vals)>1:raise RuntimeError("DUPLICATE_DIRECTORY")
 return vals[0] if vals else None
def scan(blob,name):
 info={"native_sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob),"file_extension":pathlib.Path(name).suffix.lower()}
 if blob.startswith(b"PK\x03\x04"):
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   vals=[v for v in z.infolist() if not v.is_dir()]
   info.update(native_format="ZIP",zip_members=len(vals),
    member_formats=sorted({pathlib.Path(v.filename).suffix.lower() for v in vals}),
    schema_state="ZIP_ENVELOPE_ONLY")
   if len(vals)<=30 and sum(v.file_size for v in vals)<=1500000:
    members=[]
    for m in vals[:12]:
     if ".." in pathlib.PurePosixPath(m.filename).parts or m.file_size>150000:continue
     mem=scan(z.read(m),m.filename) if not m.filename.lower().endswith(".zip") else {"schema_state":"NESTED_ZIP"}
     members.append({"suffix":pathlib.Path(m.filename).suffix.lower(),"fields":mem.get("fields",[]),
      "file_format":mem.get("native_format"),"sha256":mem.get("native_sha256"),"date_samples":mem.get("date_samples",[])})
    info["member_schemas"]=members
   return info
 if blob.startswith((b"\xd0\xcf\x11\xe0",b"PK\x03\x04")) or name.lower().endswith((".xls",".xlsx")):
  return {**info,"native_format":"EXCEL_BINARY","schema_state":"NOT_PARSED"}
 for encoding in ("utf-8-sig","cp950","big5"):
  try:s=blob.decode(encoding);break
  except UnicodeDecodeError:continue
 else:return {**info,"native_format":"BINARY","schema_state":"UNREADABLE_ENCODING"}
 info["encoding"]=encoding;raw=s.lstrip()
 if raw.startswith(("{","[")):
  try:
   obj=json.loads(raw)
   rs=obj if isinstance(obj,list) else obj.get("data",obj.get("tables",[])) if isinstance(obj,dict) else []
   if not isinstance(rs,list):rs=[]
   fields=sorted({str(k) for row in rs[:200] if isinstance(row,dict) for k in row})
   info.update(native_format="JSON",schema_state="JSON_PARSED",fields=fields,record_count=len(rs),
    date_samples=sorted({str(row.get("date") or row.get("trade_date") or "")[:10] for row in rs[:1000] if isinstance(row,dict) and (row.get("date") or row.get("trade_date"))})[:50])
   return info
  except ValueError:return {**info,"native_format":"JSON","schema_state":"JSON_PARSE_FAILED"}
 if raw.lower().startswith(("<!doctype","<html","<table")):
  return {**info,"native_format":"HTML","schema_state":"HTML_SOURCE_NOT_NORMALIZED","fields":[]}
 sep="\t" if s.splitlines()[0].count("\t")>s.splitlines()[0].count(",") else ","
 try:
  rs=list(csv.reader(io.StringIO(s[:1500000]),delimiter=sep))
  fields=rs[0][:80] if rs else []
  info.update(native_format="TSV" if sep=="\t" else "CSV",fields=fields,
    record_count=max(len(rs)-1,0),schema_state="DELIMITED_PARSED",
    date_samples=sorted({row[0][:10] for row in rs[1:] if row and re.match(r"20\d\d[-/]\d\d[-/]\d\d",row[0])})[:50])
  return info
 except csv.Error:return {**info,"native_format":"TEXT","schema_state":"CSV_PARSER_FAILED"}
def official():
 token=auth()
 root=json.loads(get("https://www.googleapis.com/drive/v3/files/"+BROOT+"?fields=name,parents",{"Authorization":"Bearer "+token}))
 if root.get("name")!="20_BRONZE" or C1 not in root.get("parents",[]):raise RuntimeError("BRONZE_ROOT_IDENTITY_MISMATCH")
 contract=list(csv.DictReader(io.StringIO(get(RAW).decode("utf-8-sig"))))
 datasets=[v for v in contract if v["source_class_id"]==SOURCE]
 year=find_named(BROOT,"2026",token)
 src=find_named(year["id"],SOURCE,token) if year else None
 files=[];folders=0;pagination_complete=True
 if src:
  queue=[(src,0)]
  while queue and folders<45 and len(files)<1600:
   folder,depth=queue.pop(0);folders+=1
   nodes,complete=children(folder["id"],token)
   pagination_complete &= complete
   for n in nodes:
    if n["mimeType"]==MIME and depth<3:queue.append((n,depth+1))
    elif n["mimeType"]!=MIME:files.append(n)
 # Date can be from path or inside content; filename is only weak evidence.
 examples=[];byday={d:[] for d in DAYS}
 scored=sorted(files,key=lambda f:(0 if any(d in f["name"] or d.replace("-","") in f["name"] for d in DAYS) else 1,
  int(f.get("size") or 0)))
 for f in scored[:25]:
  filename=f["name"];size=int(f.get("size") or 0)
  filename_days=[d for d in DAYS if d in filename or d.replace("-","") in filename]
  if size>1500000:
   examples.append({"file_format":pathlib.Path(filename).suffix.lower(),"size":size,"status":"SIZE_LIMIT","from_filename_days":filename_days});continue
  try:
   b=get("https://www.googleapis.com/drive/v3/files/"+f["id"]+"?alt=media",{"Authorization":"Bearer "+token},limit=1500000)
   info=scan(b,filename);info["from_filename_days"]=filename_days
   # Do not include raw file names or Drive IDs in PUBLIC reports.
   evidence_days=[d for d in DAYS if d in info.get("date_samples",[])]
   for nested in info.get("member_schemas",[]):
    evidence_days += [d for d in DAYS if d in nested.get("date_samples",[])]
   info["days_verified_by_content"]=sorted(set(evidence_days))
   for day in info["days_verified_by_content"]:byday[day].append({"native_format":info["native_format"],"fields":info.get("fields",[]),"sha256":info["native_sha256"]})
   examples.append(info)
  except Exception as e:
   examples.append({"status":"SAMPLE_READ_OR_PARSE_ERROR","error_type":type(e).__name__,"from_filename_days":filename_days})
 rows=[]
 for dataset in datasets:
  rows.append({"source":SOURCE,"dataset":dataset["dataset_id"],"catalog_status":"V095_CANDIDATE",
   "documented_start":"UNKNOWN_FOR_THIS_DATASET","observed_start":"NOT_CERTIFIED",
   "observed_end":"NOT_CERTIFIED","latest_published":"NOT_CERTIFIED",
   "raw_format_candidate":dataset.get("raw_format"),"primary_keys_candidate":dataset.get("primary_keys"),
   "original_unit":dataset.get("native_unit"),"PIT_rule":"PUBLICATION_DAY_PLUS_ONE",
   "five_day_evidence":"NATIVE_SOURCE_LEVEL_SAMPLES_ONLY_NOT_DATASET_MAPPED",
   "G1_G2_G3_G4":"NOT_CERTIFIED"})
 return {"source":SOURCE,"five_days":DAYS,"official_contract_count":len(rows),
  "source_file_candidates_in_bounded_tree":len(files),"folder_count":folders,
  "folder_pagination_complete":pagination_complete,"five_day_source_evidence":{d:{"content_verified_sample_count":len(byday[d]),
    "status":"CONTENT_DATE_OBSERVED" if byday[d] else "NO_DATE_EVIDENCE_IN_BOUNDED_SAMPLES"} for d in DAYS},
  "native_examples":examples,"dataset_registry":rows,"full_dataset_enumeration":False,
  "full_historical_coverage":False,"source_api_document_comparison":"CANDIDATE_ONLY_NOT_OFFICIAL_COLUMN_CERTIFIED"}
def finmind():
 doc=get(FIN_DOC).decode("utf-8-sig")
 candidates=[]
 for block in re.split(r"(?m)^### ",doc)[1:]:
  ds=block.splitlines()[0].strip()
  tier=re.search(r"(?m)^-\s*\*\*Tier:\*\*\s*(.+)$",block)
  req=re.search(r"(?m)^-\s*\*\*Required:\*\*\s*(.+)$",block)
  cols=re.search(r"(?m)^-\s*\*\*Key columns:\*\*\s*(.+)$",block)
  if tier and req and tier.group(1).strip() in ("Free","Free(w/ data_id)"):
   candidates.append((ds,tier.group(1).strip(),req.group(1),cols.group(1) if cols else ""))
 rows=[]
 # limit: 54*5=270 request on anonymous Free, must respect 300/h budget. Skip known paid-only.
 for ds,tier,required,col in candidates:
  tests=[]
  for day in DAYS:
   query={"dataset":ds,"start_date":day}
   if "data_id" in required:query["data_id"]=("TAIEX" if ds=="TaiwanStockTotalReturnIndex" else
     "WTI" if ds=="CrudeOilPrices" else "United States 10-Year" if ds=="GovernmentBondsYield" else
     "AAPL" if ds.startswith("US") else "TX" if "Futures" in ds else "TXO" if "Option" in ds else "2330")
   if "single day" not in required.lower():query["end_date"]=day
   try:
    req=urllib.request.Request("https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode(query),
      headers={"User-Agent":"JARVIS-v098-FREE-8-source-readonly"})
    with urllib.request.urlopen(req,timeout=32) as resp:
     status=resp.status;raw=resp.read(2500001)
    if len(raw)>2500000:result={"state":"SIZE_LIMIT"}
    else:
     obj=json.loads(raw.decode("utf-8-sig"));data=obj.get("data",[])
     if obj.get("status")!=200:result={"state":"API_REJECTED","api_status":obj.get("status")}
     elif not isinstance(data,list):result={"state":"BAD_SHAPE"}
     elif not data:result={"state":"EMPTY","rows":0}
     else:
      fields=sorted({str(k) for x in data[:300] if isinstance(x,dict) for k in x})
      typ={k:sorted({type(x[k]).__name__ for x in data if isinstance(x,dict) and k in x}) for k in fields}
      result={"state":"PASS","rows":len(data),"fields":fields,"field_types":typ,
        "min_date":min(str(x.get("date","")) for x in data if isinstance(x,dict)),
        "max_date":max(str(x.get("date","")) for x in data if isinstance(x,dict)),
        "canonical_sha256":hashlib.sha256(json.dumps(sorted(data,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)),
            sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()}
   except urllib.error.HTTPError as e:result={"state":"HTTP_ERROR","http_status":e.code}
   except Exception as e:result={"state":"REQUEST_ERROR","error_type":type(e).__name__}
   tests.append({"day":day,"query":query,"result":result})
   if result.get("http_status")==429:break
   time.sleep(.32)
  rows.append({"source":SOURCE,"dataset":ds,"tier":tier,"official_key_columns":col,
   "trading_day_samples":tests,"historical_first":"UNVERIFIED_BY_5D_TEST",
   "historical_last":"UNVERIFIED_BY_5D_TEST","all_symbols_complete":False})
  print("SOURCE_PROGRESS "+json.dumps({"source":SOURCE,"dataset":ds,"tested_days":len(tests),
     "pass":sum(x["result"]["state"]=="PASS" for x in tests)},ensure_ascii=False),flush=True)
 return {"source":SOURCE,"five_days":DAYS,"registry_version_sha256":hashlib.sha256(doc.encode()).hexdigest(),
   "candidate_datasets":len(rows),"dataset_registry":rows,
   "official_catalog_vs_tier_pricing_count":"NOT_RECONCILED","historical_dates":"IMPORT_R2_EVIDENCE_SEPARATELY",
   "all_history_complete":False}
def main():
 report={"schema":"JARVIS_V098_EIGHT_SOURCE_FIVE_DAY_LANE_V1","run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
  "source":SOURCE,"five_days":DAYS,"Bronze_mutated":False,"Silver_Gold_run":False}
 try:report.update(finmind() if SOURCE=="FinMind_Free" else official())
 except Exception as err:report["lane_error"]={"type":type(err).__name__}
 (ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print("JARVIS_SOURCE_LANE_FINAL "+json.dumps({"source":SOURCE,"rows":len(report.get("dataset_registry",[])),
  "error":report.get("lane_error"),"five_days":DAYS,"safe":True},ensure_ascii=False),flush=True)
 if report.get("lane_error"):raise SystemExit(1)
if __name__=="__main__":main()
