import io,json,os,pathlib,collections
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 s=build("drive","v3",credentials=c,cache_discovery=False)
 parent="1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U"
 q=s.files().list(q="'"+parent+"' in parents and name = '2026-09_CANDIDATE_98_GATE' and trashed = false",fields="files(id,name)").execute().get("files",[])
 status={"folder_count":len(q),"acceptance":"NOT_VERIFIED"}
 if len(q)==1:
  fs=s.files().list(q="'"+q[0]["id"]+"' in parents and trashed = false",fields="files(id,name,size)",pageSize=100).execute().get("files",[])
  selected=[x for x in fs if x["name"]=="JARVIS_v095_202609_TDCC_OWNERSHIP_CANDIDATE_R1.parquet"]
  status["matching_parquet_count"]=len(selected)
  if len(selected)==1:
   t=pq.read_table(io.BytesIO(s.files().get_media(fileId=selected[0]["id"]).execute()),columns=["snapshot_date","stock_id","holding_tier"])
   weeks=collections.Counter(t.column("snapshot_date").to_pylist())
   status.update(rows=t.num_rows,weeks=dict(weeks),file_id=selected[0]["id"],acceptance="MONTH_ONLY_SILVER_PASS" if t.num_rows==276097 and set(weeks)=={"2026-09-04","2026-09-11","2026-09-18","2026-09-24"} else "ROW_OR_WEEK_MISMATCH")
 pathlib.Path("monthly_r4").mkdir(exist_ok=True)
 pathlib.Path("monthly_r4/tdcc_check.json").write_text(json.dumps(status,ensure_ascii=False,indent=2))
 print(json.dumps(status,ensure_ascii=False))
if __name__=="__main__":main()
