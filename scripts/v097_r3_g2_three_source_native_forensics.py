"""R3 G2 deep forensic comparison: 3 source x 10 frozen native samples.

Format fingerprint, source byte SHA, ZIP CRC, native HTML table rows,
MOPS document/query identity, TDCC tier/security/date schema, TAIFEX actual
CSV 10/11 columns, footer, rows, trader classes and primary-key semantics.
Stores full sample-level provenance / exact discrepancy and remediation in
isolated Drive. Never auto-approve unverified historical official versions.
"""
from __future__ import annotations
import collections,csv,hashlib,io,json,os,re,zipfile,datetime
from bs4 import BeautifulSoup
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCES=("MOPS","TDCC","TAIFEX")
INPUT="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
PRIOR="44261840978"
FOLDER="R3_G2_THREE_SOURCE_NATIVE_OFFICIAL_DEEP_DIAG_ISOLATED"
MAX_FILE=8_000_000
MAX_ZIP=24_000_000
OFFICIAL={
 "MOPS":{"document":"https://mopsfin.twse.com.tw/","review_points":["financial report period","issuer identity","filing revision/PIT","table metric units"]},
 "TDCC":{"document":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock","review_points":["weekly asof","effective security type","tier labels","shareholder counts/shares/ratios"]},
 "TAIFEX":{"document":"https://www.taifex.com.tw/file/taifex/CHINESE/11/TechDocs/30/opendata_all.pdf","review_points":["CSV 10-column futures vs 11-column options","date and product class","0/1 trader type","- / 666666 / 999999 footer semantics"]}
}
def decode(data):
 for codec in ("utf-8-sig","cp950","big5"):
  try:return data.decode(codec),codec
  except UnicodeError:continue
 return None,None
def field_clean(x):return " ".join(x.replace("\u3000"," ").split())
def parse_table(text):
 soup=BeautifulSoup(text,"html.parser")
 tables=[]
 for t in soup.find_all("table")[:8]:
  rows=[]
  for tr in t.find_all("tr")[:12]:
   vals=[field_clean(e.get_text(" ",strip=True))[:110] for e in tr.find_all(["th","td"],recursive=False)]
   if vals:rows.append(vals[:22])
  if rows:tables.append({"headers_candidates":rows[:3],"first_rows":rows[3:6],
                          "table_row_count":len(t.find_all("tr")),"table_column_counts":{str(k):v for k,v in collections.Counter(map(len,rows)).items()}})
 return soup,tables
def profile_html(src,data,name):
 text,codec=decode(data)
 info={"native_member":name,"member_sha256":hashlib.sha256(data).hexdigest(),
       "native_format":"HTML_OR_XML","encoding":codec,"bytes":len(data)}
 if text is None:return {**info,"hold":"UNREADABLE_NATIVE_BYTES"}
 soup,tables=parse_table(text)
 title=soup.title.get_text(" ",strip=True)[:160] if soup.title else None
 content=soup.get_text(" ",strip=True)
 info.update({"title":title,"table_count":len(soup.find_all("table")),
              "sample_tables":tables[:4],
              "date_fragments":list(dict.fromkeys(re.findall(r"(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}",content)))[:15],
              "security_code_candidates":list(dict.fromkeys(re.findall(r"(?<!\d)[1-9]\d{3}(?!\d)",content)))[:15],
              "native_form_actions":[{"method":(x.get("method") or "GET").upper(),
               "action":str(x.get("action") or "")[:220]} for x in soup.find_all("form")[:4]],
              "html_charset_declared":[x.get("charset") for x in soup.find_all("meta") if x.get("charset")][:3]})
 if src=="TDCC":
  labels=[field_clean(x.get_text(" ",strip=True)) for x in soup.find_all(["th","td"])]
  tokens=("持股","分級","人數","股數","比例","占集保庫存","週","日期","證券代號")
  info["TDCC_official_semantic_label_presence"]={k:any(k in x for x in labels) for k in tokens}
  info["row_width_signatures"]=[t["table_column_counts"] for t in tables[:4]]
  info["tier_candidates"]=list(dict.fromkeys(x for x in labels if re.search(r"以上|以下|至|級距|分級",x)))[:22]
  info["hold_reason"]="OFFICIAL_WEEKLY_SECURITY_ID_AND_TIER_ERA_NOT_BOUND_TO_THIS_SOURCE"
 else:
  labels=[field_clean(x.get_text(" ",strip=True)) for x in soup.find_all(["th","td"])]
  info["MOPS_financial_metric_label_presence"]={k:any(k in x for x in labels)
    for k in ("資產","負債","權益","營業收入","營收","損益","本期淨利","公司代號","查詢")}
  info["form_input_names"]=list(dict.fromkeys(x.get("name") for x in soup.find_all(["input","select"]) if x.get("name")))[:35]
  info["hold_reason"]="MOPS_FILING_ID_REPORT_TYPE_AMENDMENT_PIT_OFFICIAL_BYTES_UNBOUND"
 return info
def profile_csv(data,name):
 text,codec=decode(data)
 info={"native_member":name,"member_sha256":hashlib.sha256(data).hexdigest(),
       "native_format":"CSV","encoding":codec,"bytes":len(data)}
 if text is None:return {**info,"hold":"UNREADABLE_CSV_ENCODING"}
 try:rows=list(csv.reader(io.StringIO(text)))
 except csv.Error as e:return {**info,"hold":"CSV_PARSE_ERROR","detail":str(e)}
 nonempty=[r for r in rows if any(x.strip() for x in r)]
 header=nonempty[0] if nonempty else []
 dat=[r for r in nonempty[1:] if r and re.fullmatch(r"20\d{2}/\d{2}/\d{2}",r[0].strip())]
 foot=[r for r in nonempty[1:] if r not in dat]
 cols=len(header)
 fields=[field_clean(c) for c in header]
 info.update({"native_header":fields,"native_column_count":cols,"native_nonempty_rows":len(nonempty),
  "actual_trade_rows":len(dat),"footer_note_count":len(foot),
  "footer_original":foot[:4],"data_width_distribution":dict(collections.Counter(map(len,dat))),
  "first_two_data_rows":dat[:2],"last_two_data_rows":dat[-2:],
  "date_count":len({r[0] for r in dat}),
  "date_min":min((r[0] for r in dat),default=None),
  "date_max":max((r[0] for r in dat),default=None),
  "product_codes":len({r[1] for r in dat if len(r)>1}),
  "native_zero_cells":sum(c.strip()=="0" for r in dat for c in r[5:]),
  "native_dash_cells":sum(c.strip()=="-" for r in dat for c in r[5:]),
  "native_blank_cells":sum(c.strip()=="" for r in dat for c in r[5:])})
 if cols==10 and "交易人類別" in fields and "全市場未沖銷部位數" in fields:
  info["dataset_candidate"]="TAIFEX_LARGE_TRADER_FUTURES_10"
 elif cols==11 and "交易人類別" in fields and "全市場未沖銷部位數" in fields:
  info["dataset_candidate"]="TAIFEX_LARGE_TRADER_OPTIONS_11"
 else:info["dataset_candidate"]="OTHER_TAIFEX_DATASET_MUST_HAVE_OWN_NATIVE_CONTRACT"
 info["semantic_header_field_match"]=(info["dataset_candidate"] in ("TAIFEX_LARGE_TRADER_FUTURES_10","TAIFEX_LARGE_TRADER_OPTIONS_11"))
 info["historical_original_source_byte_sha_verified"]=False
 info["hold_reason"]="NO_EXACT_INDEPENDENT_OFFICIAL_HISTORICAL_RESPONSE_OR_EFFECTIVE_VERSION"
 return info
def profile_native(src,blob,source_path):
 details={"outer_sha256":hashlib.sha256(blob).hexdigest(),"archive_format":"DIRECT",
          "outer_bytes":len(blob),"members":[]}
 if zipfile.is_zipfile(io.BytesIO(blob)):
  details["archive_format"]="ZIP"
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   items=[x for x in z.infolist() if not x.is_dir()]
   details["member_count"]=len(items)
   details["expanded_bytes"]=sum(x.file_size for x in items)
   if len(items)>120 or details["expanded_bytes"]>MAX_ZIP:
    details["guard"]="HOLD_ZIP_ARCHIVE_RESOURCE_BOUND";return details
   if z.testzip() is not None:details["guard"]="HOLD_ZIP_CRC";return details
   pairs=[(e.filename,z.read(e)) for e in items if e.file_size<=2_500_000][:18]
 else:pairs=[(str(source_path),blob)]
 details["guard"]="PASS_NATIVE_OUTER_CRC_AND_SHA"
 for name,data in pairs:
  txt,_=decode(data)
  if (txt or "").lstrip().startswith("<"):
   p=profile_html(src,data,name)
  elif src=="TAIFEX":p=profile_csv(data,name)
  else:
   p={"native_member":name,"bytes":len(data),"member_sha256":hashlib.sha256(data).hexdigest(),
      "native_format":"JSON_OR_TEXT","sample":(txt or "")[:180],
      "hold_reason":"SAMPLE_NOT_RECOGNIZED_NATIVE_REPORT_FORMAT"}
  details["members"].append(p)
 return details

def main():
 api,control,quality,match,load,_,_,call=source_api()
 prev=match(api,quality,INPUT)
 if not prev:raise RuntimeError("PRIOR_30_SOURCE_REAL_SAMPLE_FOLDER_MISSING")
 output=match(api,quality,FOLDER)
 if output is None:output=call(lambda:api.files().create(
  body={"name":FOLDER,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"},
  fields="id,mimeType"))
 if output.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("OUTPUT_NOT_A_FOLDER")
 summaries=[]
 for src in SOURCES:
  baseline=read_baseline(api,quality,match,load,src);assert_cohort(baseline,src)
  idx={x["source_id"]:x for x in baseline}
  pf=match(api,prev["id"],f"r3_g2_pilot_{src}_10_run_{PRIOR}.json")
  if not pf:raise RuntimeError("SOURCE_NATIVE_10_SAMPLE_RECEIPT_MISSING_"+src)
  samples=load(api,pf["id"])["samples"]
  if len(samples)!=10:raise RuntimeError("ACTUAL_SOURCE_SAMPLE_COUNT_NOT_TEN")
  result=[];counts=collections.Counter();distributions=collections.Counter()
  for smp in samples:
   row=idx.get(smp["source_id"])
   if row is None:raise RuntimeError("ORPHAN_FROZEN_SOURCE_ID")
   profile={"source_id":row["source_id"],"source_sha256":row["source_sha256"],
    "source_path":row.get("source_path"),"G2":"HOLD","G2_official_template_approved":False}
   try:
    meta=call(lambda:api.files().get(fileId=row["destination_id"],fields="id,size,mimeType"))
    if int(meta.get("size") or 0)>MAX_FILE:
     profile["hold_reason"]="BOUNDED_FILE_SIZE_FOR_REVIEW"
    else:
     blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
     profile["outer_sha_match"]=hashlib.sha256(blob).hexdigest()==row["source_sha256"]
     if not profile["outer_sha_match"]:raise RuntimeError("BRONZE_SOURCE_HASH_MISMATCH")
     native=profile_native(src,blob,row.get("source_path"))
     profile["native"]=native
     allmembers=native["members"]
     counts["SAMPLE_SOURCE_SHA_MATCH"]+=1
     for m in allmembers:
      distributions[m.get("dataset_candidate",m.get("native_format","UNKNOWN"))]+=1
     profile["hold_reason"]=(allmembers[0].get("hold_reason","UNCERTIFIED_NATIVE_DATASET_OR_ERA")
       if allmembers else "NO_NATIVE_MEMBERS_REVIEWED")
   except Exception as e:
    profile["hold_reason"]="SOURCE_READ_OR_PARSE_EXCEPTION_"+type(e).__name__
   counts["HOLD:"+profile["hold_reason"]]+=1
   result.append(profile)
  report={"schema":"R3_G2_THREE_SOURCE_30_NATIVE_FORENSIC_DIAGNOSTIC_V1",
   "source":src,"run":RUN,"source_cohort":len(baseline),
   "sample_real_frozen":10,"official_reference":OFFICIAL[src],
   "profiles":result,"format_distributions":dict(distributions),
   "result_counts":dict(counts),"formal_g2_issued":0,"g2_hold":10,
   "source_format_candidates_not_certified_as_official_era":True,
   "bronze_modified":False,"silver_gold_materialized":False}
  name=f"r3_g2_30_source_forensic_{src}_run_{RUN}.json"
  rid=put_once(api,output["id"],name,report)
  if load(api,rid)!=report:raise RuntimeError("GOOGLE_DRIVE_SOURCE_FORENSIC_READBACK_FAIL")
  summary={"source":src,"samples":10,"outer_sha_pass":counts["SAMPLE_SOURCE_SHA_MATCH"],
   "native_types":dict(distributions),"hold_count":10,
   "receipt_id":rid,"readback":True}
  summaries.append(summary)
  print("R3_G2_THREE_FORENSIC_SOURCE="+json.dumps(summary,sort_keys=True,ensure_ascii=False),flush=True)
 master={"schema":"R3_G2_THREE_SOURCE_30_FORENSIC_MASTER_V1","run":RUN,
    "source_summaries":summaries,"formal_g2_pass":0,"formal_hold":30,
    "previous_324_G2_QA_unmodified":True,"bronze_modified":False,
    "silver_gold_materialized":False}
 name=f"r3_g2_three_source_30_forensic_master_run_{RUN}.json"
 mid=put_once(api,output["id"],name,master)
 if load(api,mid)!=master:raise RuntimeError("MASTER_READBACK_FAIL")
 print("R3_G2_THREE_FORENSIC_MASTER="+json.dumps({"run":RUN,"master_id":mid,
   "sources":summaries,"readback":True},sort_keys=True,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
