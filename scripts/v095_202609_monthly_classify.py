import io,json,os,collections,pathlib
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
SRC={"TSE":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz","OTC":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk"}
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 s=build("drive","v3",credentials=c,cache_discovery=False)
 result={}
 for market,id in SRC.items():
  table=pq.read_table(io.BytesIO(s.files().get_media(fileId=id).execute()))
  groups=collections.Counter();examples=[]
  for r in table.to_pylist():
   if all(r.get(k) is not None for k in ("open","high","low","close")):groups["NUMERIC"]+=1;continue
   volume=r.get("volume_shares")
   label="NO_TRADE_CANDIDATE" if volume==0 else "POSITIVE_VOLUME_UNEXPLAINED" if volume is not None and volume>0 else "UNKNOWN_VOLUME"
   groups[label]+=1
   native=r.get("raw_ohlc_json","")
   groups["NATIVE_PATTERN_"+str(native)[:70]]+=1
   if len(examples)<20:examples.append({"date":str(r["trade_date"]),"stock_id":r["stock_id"],"status":label,"volume":volume,"turnover_億元":str(r.get("turnover_億元")),"native":native})
  result[market]={"counts":dict(groups),"sample":examples}
 pathlib.Path("monthly_r4").mkdir(exist_ok=True)
 pathlib.Path("monthly_r4/classification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
