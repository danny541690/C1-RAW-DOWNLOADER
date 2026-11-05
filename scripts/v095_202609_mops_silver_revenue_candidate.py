"""September 2026 MOPS revenue Bronze original CP950 HTML -> isolated Silver Parquet.
Preserve all four original documents, native thousand-NTD units and raw notes.
"""
import os,json,zipfile,io,re,html,decimal,hashlib,collections,pathlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
SRC="1wAHL6qfZnSC3RIKvShhL4At3ZNs32bvj"
DEST="1ick4kRSlmz1ukibDq3TOD7QQxiBHtzWb"
MONTH="2026-09_CANDIDATE_98_GATE";D=decimal.Decimal
def sha(b):return hashlib.sha256(b).hexdigest()
def number(s):
 x=str(s).strip().replace(",","").replace("−","-")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",x):return None
 return D(x)
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def clean(s):
 return html.unescape(re.sub(r"<[^>]*>","",s)).strip()
def save(s,parent,name,data):
 f=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=50).execute()["files"]
 if len(f)>1:raise ValueError("AMBIGUOUS_DEST")
 if f:
  if sha(get(s,f[0]["id"]))!=sha(data):raise ValueError("EXISTING_FILE_CONFLICT")
  return f[0]["id"]
 x=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(get(s,x))!=sha(data):raise ValueError("UPLOAD_SHA_READBACK_MISMATCH")
 return x
def main():
 s=svc();z=zipfile.ZipFile(io.BytesIO(get(s,SRC)))
 if z.testzip() is not None:raise ValueError("ORIGINAL_ZIP_CRC_FAIL")
 m=json.loads(z.read("manifest.json"));units=[x for x in m["units"] if x["name"].startswith(("revenue_sii_","revenue_otc_"))]
 if len(units)!=4:raise ValueError("NOT_FOUR_REVENUE_ORIGINALS")
 records=[];seen=set();per=collections.Counter();issues=[]
 for x in units:
  name=x["file"].split("/")[-1];b=z.read(name)
  if sha(b)!=x["sha256"]:raise ValueError("MOPS_NATIVE_SHA_MISMATCH")
  document=b.decode("cp950")
  market="TSE" if "revenue_sii_" in x["name"] else "OTC"
  if "115年9月份" not in document:raise ValueError("WRONG_REVENUE_MONTH")
  count=0
  for tr in re.findall(r"<tr\b[^>]*\balign\s*=\s*['\"]?right['\"]?[^>]*>(.*?)</tr>",document,flags=re.I|re.S):
   cells=[clean(y) for y in re.findall(r"<td\b[^>]*>(.*?)</td>",tr,flags=re.I|re.S)]
   if len(cells)!=11 or not re.fullmatch(r"\d{4}",cells[0]):continue
   key=(market,cells[0])
   if key in seen:raise ValueError("MOPS_DUPLICATE_COMPANY_PER_MARKET")
   seen.add(key);count+=1
   fields=["current_month","previous_month","year_ago_month","mom_pct_reported","yoy_pct_reported","ytd","year_ago_ytd","ytd_yoy_pct_reported"]
   nums=[number(v) for v in cells[2:10]]
   if nums[0] is None:issues.append({"stock_id":cells[0],"market":market,"reason":"NATIVE_NONNUMERIC_REVENUE"})
   row=dict(revenue_month="2026-09",stock_id=cells[0],market=market,name=cells[1],
     native_unit="千元",raw_note=cells[10],source="MOPS",source_zip_id=SRC,
     native_member=name,native_sha256=sha(b),available_at=None,published_at=None,
     pit_verified=False,status="CANDIDATE_REVENUE_PIT_UNVERIFIED")
   for k,v in zip(fields,nums):
    row[k]=str(v) if v is not None else None
   for key_in,key_out in (("current_month","revenue_億元"),("previous_month","prior_month_億元"),("year_ago_month","year_ago_month_億元"),("ytd","ytd_億元"),("year_ago_ytd","year_ago_ytd_億元")):
    vv=number(row[key_in]) if row[key_in] is not None else None
    row[key_out]=str(vv/D("100000")) if vv is not None else None
   records.append(row)
  per[x["name"]]=count
  if count!=x["rows"]:raise ValueError("MOPS_REPORT_ROW_COUNT_DIFFERENCE_"+x["name"]+"_"+str(count))
 a=s.files().list(q=f"'{DEST}' in parents and name = '{MONTH}' and trashed = false",fields="files(id)",pageSize=50).execute()["files"]
 if len(a)>1:raise ValueError("AMBIGUOUS_MONTH")
 folder=a[0]["id"] if a else s.files().create(body={"name":MONTH,"mimeType":"application/vnd.google-apps.folder","parents":[DEST]},fields="id").execute()["id"]
 out=io.BytesIO();pq.write_table(pa.Table.from_pylist(records),out,compression="zstd")
 b=out.getvalue();assert pq.read_metadata(io.BytesIO(b)).num_rows==len(records)
 par=save(s,folder,"JARVIS_v095_SILVER_202609_MOPS_REVENUE_CANDIDATE_R1.parquet",b)
 report=dict(schema="JARVIS_V095_202609_MOPS_SILVER_REVENUE",month="2026-09",
    rows=len(records),per_source_unit_rows=dict(per),original_count=4,
    parquet_drive_id=par,parquet_sha256=sha(b),native_revenue_unit="千元",
    analysis_money_unit="億元",status="SILVER_CANDIDATE_ONLY",pit_verified=False,gold_allowed=False,
    completeness_to_all_mops_fundamental_datasets=False,exceptions=issues[:50],
    pending=["official publication/revision timestamps","historical security identity","all MOPS disclosure & financial datasets outside monthly revenue"])
 qa=save(s,folder,"JARVIS_v095_SILVER_202609_MOPS_REVENUE_QA_R1.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
 report["qa_drive_id"]=qa
 pathlib.Path("v095_silver_mops_202609").mkdir(exist_ok=True)
 pathlib.Path("v095_silver_mops_202609/result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
