import json,io,os,collections,argparse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pyarrow.parquet as pq
FILES={"TWSE_institutional":"1lc_j_auacRUuUBjSvMqUHvOHlAXbvgkg",
"TPEx_institutional":"1-31-lNq_IL2gxDN8u_upzFmIM3ZznKQe",
"TWSE_margin":"1R9WquaNOM1kFhVMaLWX_IOnePgsGAuCb","TPEx_margin":"15NAXldOBytuX1RQz1W7ko84pPBy6ymku",
"TWSE_lending":"1fnfY_2Levs5xZw-Q6tM62BsJrQc9sFXb","TPEx_lending":"1H_cVfenqS96zz7XpTxYgrNydwc7qwTf_",
"TWSE_valuation":"1HxpjvcKCoh7J3H6BUDV0CRdI84wT-d4O","TPEx_valuation":"17unNKYbVBPUiFAHZERUu-Vbr_0CKHiIO",
"TWSE_foreign_holdings":"1uxUgBmTVfzwH3ibNxWJuLvHIj7M9znTG","TPEx_foreign_holdings":"19pyMQqaVvrY6rcMU806e3a5mR5MtLr0q"}
def main():
 creds=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 creds.refresh(Request());svc=build("drive","v3",credentials=creds,cache_discovery=False)
 p=argparse.ArgumentParser();p.add_argument("--market",choices=["TWSE","TPEx"],required=True);a=p.parse_args()
 for k,id in FILES.items():
  if not k.startswith(a.market):continue
  b=svc.files().get_media(fileId=id).execute();t=pq.read_table(io.BytesIO(b))
  row=t.slice(0,min(t.num_rows,2)).to_pylist()
  sample=[{"date":r.get("trade_date"),"native_fields":json.loads(r["native_fields_json"])[:38],"native_row":list(json.loads(r["native_row_json"]).items())[:30],"table":r.get("table_title")} for r in row]
  print(json.dumps({"group":k,"row_count":t.num_rows,"sample":sample},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
