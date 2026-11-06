import json,os,io,collections,pathlib,re,hashlib
from googleapiclient.http import MediaIoBaseUpload
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
S={"TSE":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz","OTC":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk"}
G={"tse":"1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI","revenue":"1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI","otc-price":"1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6","tse-flow":"18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7","otc-margin":"11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5"}
CAT="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
OUT=pathlib.Path("r5_monthly");OUT.mkdir(exist_ok=True)
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 d=build("drive","v3",credentials=c,cache_discovery=False)
 read=lambda fid:d.files().get_media(fileId=fid).execute()
 prices={};rows=[]
 for market,fid in S.items():
  t=pq.read_table(io.BytesIO(read(fid)));counts=collections.Counter()
  for r in t.to_pylist():
   if all(r.get(k) is not None for k in ("open","high","low","close")):counts["numeric"]+=1;continue
   v=r.get("volume_shares")
   reason="zero_volume" if v==0 else "positive_volume" if v and v>0 else "unknown"
   counts[reason]+=1
   rows.append(dict(market=market,date=str(r["trade_date"]),code=r["stock_id"],reason=reason,volume=v,native=r.get("raw_ohlc_json"),source=r.get("source_sha256")))
  prices[market]=dict(rows=t.num_rows,groups=dict(counts))
 if len(rows)!=469:raise ValueError("EXPECTED_469_EXCEPTIONS")
 cat=json.loads(read(CAT).decode("utf-8"))["indicators"]
 if len(cat)!=443:raise ValueError("EXPECTED_443_CATALOG")
 tables={k:pq.read_table(io.BytesIO(read(v))) for k,v in G.items()}
 aliases={"CLOSE":("tse","close_price_NTD"),"VOLUME":("tse","volume_shares"),"TURNOVER":("tse","turnover_億元"),"MA5":("tse","SMA_5"),"MA10":("tse","SMA_10"),"MA20":("tse","SMA_20"),"RETURN1D":("tse","close_change_1d_pct"),"AVG_VOL5D":("tse","avg_volume_shares_5"),"AVG_VOL10D":("tse","avg_volume_shares_10"),"AVG_VOL20D":("tse","avg_volume_shares_20"),"OPEN":("otc-price","open"),"HIGH":("otc-price","high"),"LOW":("otc-price","low"),"REVENUE_M0":("revenue","revenue_億元"),"REVENUE_M1":("revenue","revenue_prior_month_億元"),"REVENUE_YOY_M0":("revenue","revenue_yoy_pct"),"REVENUE_MOM_M0":("revenue","revenue_mom_pct"),"TRUST_NET_1D":("tse-flow","trust_net_shares"),"TOTAL_INST_NET_1D":("tse-flow","institutional_total_net_shares"),"MARGIN_BALANCE_1D":("otc-margin","margin_balance_lots"),"SHORT_BALANCE_1D":("otc-margin","short_balance_lots")}
 mapped=[];counts=collections.Counter()
 for i in cat:
  key=i["id"];ref=aliases.get(key)
  scope="REQUIRES_PRIOR_HISTORY" if re.search(r"(?:60|120|240)(?:D|$|_)",key) else "MONTH_POSSIBLE"
  if ref and ref[1] in tables[ref[0]].column_names:
   arr=tables[ref[0]][ref[1]];status="FIELD_EXISTS_FORMULA_UNCERTIFIED";n=len(arr)-arr.null_count
  else:status="NOT_YET_MAPPED_NOT_PROVEN_MISSING";n=0
  counts[status]+=1;mapped.append(dict(id=key,scope=scope,status=status,field=ref,non_null_rows=n))
 report=dict(period="2026-09",price=prices,exception_count=len(rows),catalog_count=len(cat),
  gold_mapping=dict(counts),historical_pit="NOT_CERTIFIED",september_revenue_asof_0930="NOT_KNOWN",
  long_history_missing_is_not_month_failure=True,official_price_repair="PENDING_SAME_SESSION_EVIDENCE")
 (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 (OUT/"price_queue.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 (OUT/"indicator_mapping.json").write_text(json.dumps(mapped,ensure_ascii=False,indent=2))
 b=(json.dumps(report,ensure_ascii=False,indent=2)+"\\n").encode()
 name="JARVIS_202609_R5_MONTHLY_QA_"+os.environ.get("GITHUB_RUN_ID","manual")+".json"
 result=d.files().create(body={"name":name,"parents":["1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json"),fields="id").execute()
 if hashlib.sha256(read(result["id"])).digest()!=hashlib.sha256(b).digest():raise ValueError("REPORT_SHA_READBACK_FAIL")
 report["drive_report_id"]=result["id"]
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
