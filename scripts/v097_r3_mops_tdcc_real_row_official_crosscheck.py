"""Crosscheck original MOPS 2025-02 OTC revenue and TDCC 2026-10-08 stock
against official historical endpoint, inspecting all native cells and row
totals. Only records genuine source-vintage G2 on verified ALL values and
historical provenance, never mere webpage 200 / header match.
"""
import collections,datetime,hashlib,io,json,os,requests,zipfile
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
OUT="R3_G2_MOPS_TDCC_ORIGINAL_CELL_OFFICIAL_CROSSCHECK_ISOLATED"
TARGETS={"MOPS":"1RYs3r-GNWnUMcg8jbAyj5UkzioqWPV5G",
         "TDCC":"1pSZLlDcTK1hPofAwesE8mcs90QPySVOw"}
def text_decode(buf):
 for enc in ("utf-8-sig","cp950","big5"):
  try:return buf.decode(enc),enc
  except UnicodeError:pass
 return None,None
def clean(s):return " ".join(s.replace("\u3000"," ").split())
def tables_from(buf):
 txt,enc=text_decode(buf)
 if txt is None:return [],enc
 soup=BeautifulSoup(txt,"html.parser")
 result=[]
 for table in soup.find_all("table"):
  rows=[]
  for tr in table.find_all("tr"):
   cells=[clean(c.get_text(" ",strip=True)) for c in tr.find_all(["th","td"],recursive=False)]
   if cells:rows.append(cells)
  if rows:result.append(rows)
 return result,enc
def tdcc_result(rows):
 table=next((t for t in rows if t and t[0][:2]==["序","持股/單位數分級"]),None)
 if not table:return {"validated_tier_table":False}
 bands=[];totals=[]
 for r in table[1:]:
  if len(r)<5:continue
  rec={"sequence":r[0],"tier":r[1],"holders":r[2],"shares":r[3],"ratio":r[4]}
  if r[0].isdigit():bands.append(rec)
  else:totals.append(rec)
 numeric=lambda x:int(x.replace(",","")) if x.replace(",","").isdigit() else None
 s_holder=sum(numeric(x["holders"]) or 0 for x in bands)
 s_shares=sum(numeric(x["shares"]) or 0 for x in bands)
 s_ratio=sum(float(x["ratio"].replace(",","")) for x in bands if x["ratio"].replace(".","",1).isdigit())
 return {"validated_tier_table":True,"tier_rows":len(bands),"total_rows":len(totals),
  "bands":[x for x in bands],"total_row":totals[:3],
  "sum_holders":s_holder,"sum_shares":s_shares,"sum_ratio_rounded":round(s_ratio,3),
  "official_total_holders_matches":any(numeric(t["holders"])==s_holder for t in totals),
  "official_total_shares_matches":any(numeric(t["shares"])==s_shares for t in totals),
  "original_tier_order":[x["tier"] for x in bands]}
def get_official(url,params=None,form=None,session=None,expected_hosts=()):
 try:
  s=session or requests.Session()
  rsp=s.post(url,data=form,timeout=19) if form is not None else s.get(url,params=params,timeout=19)
  host=(urlparse(rsp.url).hostname or "").lower()
  if expected_hosts and host not in expected_hosts:
   return {"status":"UNTRUSTED_REDIRECT","http_status":rsp.status_code},None
  data=rsp.content
  if len(data)>3_000_000:return {"status":"RESPONSE_SIZE_GUARD","http_status":rsp.status_code},None
  return {"status":"HTTP_RETRIEVED","http_status":rsp.status_code,
          "body_sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"final_host":host},data
 except requests.RequestException as exc:return {"status":"REQUEST_"+type(exc).__name__},None
def probe(src,api,quality,match,load,call):
 rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src)
 row=next((x for x in rows if x["source_id"]==TARGETS[src]),None)
 if row is None:raise RuntimeError("EXACT_FROZEN_SOURCE_ID_MISSING")
 blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:raise RuntimeError("BRONZE_BYTES_NOT_FROZEN")
 if src=="MOPS":
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   if z.testzip() is not None:raise RuntimeError("MOPS_ARCHIVE_CRC")
   name="revenue_otc_0_2025-02.html"
   raw=z.read(name)
  original_tables,enc=tables_from(raw)
  original_data=[r for t in original_tables for r in t if r and r[0].strip()=="1264"]
  origin_url="https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_114_2_0.html"
  official,response=get_official(origin_url,expected_hosts=("mopsov.twse.com.tw","mops.twse.com.tw"))
  rem_tables,rem_enc=tables_from(response) if response else ([],None)
  official_data=[r for t in rem_tables for r in t if r and r[0].strip()=="1264"]
  eq=bool(original_data and official_data and original_data==official_data)
  info={"source":"MOPS","source_id":row["source_id"],"source_sha":row["source_sha256"],
   "native_member_sha256":hashlib.sha256(raw).hexdigest(),
   "native_document_type":"OTC_MONTHLY_REVENUE_2025_02",
   "original_encoding":enc,"original_table_count":len(original_tables),
   "original_issuer_1264_rows":original_data[:3],
   "official_url":origin_url,"official_http":official,
   "official_issuer_1264_rows":official_data[:3],
   "same_issuer_complete_row_values":eq,
   "full_original_report_byte_sha_equals_current_official":bool(response and hashlib.sha256(response).hexdigest()==hashlib.sha256(raw).hexdigest()),
   "provisional_g2_status":"HOLD_UNLESS_COMPLETE_NATIVE_REPORT_AND_PIT_PROVED"}
 else:
  original_tables,enc=tables_from(blob)
  native=tdcc_result(original_tables)
  url="https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
  ses=requests.Session()
  page,html=get_official(url,session=ses,expected_hosts=("www.tdcc.com.tw","s.tdcc.com.tw"))
  params={"scaDate":"20261008","sqlMethod":"StockNo","stockNo":"2365","stockName":"","method":"submit"}
  if html:
   soup=BeautifulSoup(text_decode(html)[0] or "","html.parser")
   for inp in soup.find_all("input",{"type":"hidden"}):
    n=inp.get("name")
    if n and n in ("firDate","SYNCHRONIZER_TOKEN","SYNCHRONIZER_URI"):params[n]=inp.get("value") or ""
  post,payload=get_official(url,form=params,session=ses,expected_hosts=("www.tdcc.com.tw","s.tdcc.com.tw"))
  remote_tables,remote_enc=tables_from(payload) if payload else ([],None)
  current=tdcc_result(remote_tables)
  eq=bool(native.get("validated_tier_table") and current.get("validated_tier_table") and
          native.get("bands")==current.get("bands"))
  info={"source":"TDCC","source_id":row["source_id"],"source_sha":row["source_sha256"],
   "native_document_type":"2026-10-08_STOCK_2365_SHARE_DISTRIBUTION",
   "native_encoding":enc,"native_table_count":len(original_tables),
   "native_summary":native,"official_form_get":page,"official_form_post":post,
   "official_post_data_names_only":sorted(params),
   "official_retrieved_summary":current,
   "all_16_tier_native_cells_equal_official_response":eq,
   "provisional_g2_status":"HOLD_UNLESS_OFFICIAL_WEEK_SECURITY_ASOF_AND_PIT_PROVED"}
 info.update({"actual_formal_g2_certificate_issued":False,"bronze_modified":False,"silver_gold_materialized":False})
 return info
def main():
 api,control,quality,match,load,_,_,call=source_api()
 folder=match(api,quality,OUT)
 if not folder:folder=call(lambda:api.files().create(body={"name":OUT,"parents":[quality],
   "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 reports=[]
 for src in TARGETS:
  record=probe(src,api,quality,match,load,call)
  record=json.loads(json.dumps(record,ensure_ascii=False))
  name=f"r3_g2_{src}_real_official_row_census_run_{RUN}.json"
  id=put_once(api,folder["id"],name,record)
  if load(api,id)!=record:raise RuntimeError("SOURCE_ROWS_DRIVE_READBACK_FAILED")
  summary={"source":src,"source_id":record["source_id"],"receipt_id":id,
    "native_kind":record["native_document_type"],"official_field_cells_equal":record.get("same_issuer_complete_row_values",record.get("all_16_tier_native_cells_equal_official_response")),
    "official_http":record.get("official_http",record.get("official_form_post")),
    "readback":True}
  reports.append(summary)
  print("R3_G2_MOPS_TDCC_OFFICIAL_CELLS="+json.dumps(summary,ensure_ascii=False,sort_keys=True),flush=True)
 master={"schema":"R3_G2_MOPS_TDCC_EXACT_ORIGINAL_CELL_VS_OFFICIAL_V1","run":RUN,"records":reports,
   "new_g2_pass":0,"bronze_changed":False,"silver_gold_materialized":False}
 name=f"r3_g2_mops_tdcc_official_original_cells_master_run_{RUN}.json"
 mid=put_once(api,folder["id"],name,master)
 if load(api,mid)!=master:raise RuntimeError("MASTER_READBACK_FAIL")
 print("R3_G2_MOPS_TDCC_MASTER="+json.dumps({"run":RUN,"master":mid,"records":reports,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
