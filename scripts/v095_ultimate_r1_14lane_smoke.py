"""JARVIS v0.95 14-way read-only consolidated pilot workload.
Each GitHub matrix job is an actual independent runner, 6 Bronze + 4 Silver + 4 Gold.
Read-only metadata/provenance test; never alter existing Drive datasets.
"""
import os,json,sys,pathlib,datetime,hashlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
LANES={
 "BRONZE_TWSE":("BRONZE","1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE"),
 "BRONZE_TPEX":("BRONZE","15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG"),
 "BRONZE_MOPS":("BRONZE","1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI"),
 "BRONZE_TDCC":("BRONZE","1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-"),
 "BRONZE_TAIFEX":("BRONZE","1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz"),
 "BRONZE_NDC":("BRONZE","1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-"),
 "SILVER_PRICE":("SILVER","14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"),
 "SILVER_FUNDAMENTAL":("SILVER","1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"),
 "SILVER_TDCC":("SILVER","1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r"),
 "SILVER_MACRO":("SILVER","1uBAAcr24R0da3q0WBeFu-yc5r1HB5YfL"),
 "GOLD_TECHNICAL":("GOLD","1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI"),
 "GOLD_CHIP":("GOLD","18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7"),
 "GOLD_FINANCIAL":("GOLD","1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI"),
 "GOLD_CROSS_ASSET":("GOLD","1FYIz-uylwZLM7HL-7MG2iH90BefMyXDw")
}
def main():
 lane=os.environ.get("JARVIS_LANE","")
 if lane not in LANES:raise ValueError("Invalid lane identifier")
 group,fid=LANES[lane];out=pathlib.Path("ultimate_r1_lanes");out.mkdir(exist_ok=True)
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());s=build("drive","v3",credentials=c,cache_discovery=False)
 meta=s.files().get(fileId=fid,fields="id,name,mimeType,size,trashed,modifiedTime").execute()
 if meta.get("trashed"):raise ValueError("Drive file trashed")
 result={"run_id":os.getenv("GITHUB_RUN_ID"),"lane":lane,"stage":group,"source_id":fid,"source_meta":meta,
  "timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "scope":["2026-11","2026-10","2026-09"],"write_operations":0,
  "actual_conversion_performed":False,"pit_certified":False}
 if group=="BRONZE":
  x=s.files().list(q="'"+fid+"' in parents and trashed=false",fields="nextPageToken,files(name,id,mimeType)",pageSize=1000).execute()
  months={a["name"]:a["id"] for a in x.get("files",[]) if a.get("mimeType")=="application/vnd.google-apps.folder"}
  result["pilot_months"]={month:{"exists":month in months,"month_folder_id":months.get(month)} for month in result["scope"]}
 else:
  result["availability"]="EXISTS_CANDIDATE_NOT_CERTIFIED"
  # Check that the Gold catalog is accessible; this is not formula/PIT certification.
  if group=="GOLD":
   catalog=s.files().get(fileId="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7",fields="id,name,size,trashed").execute()
   result["catalog_accessible"]=not catalog.get("trashed")
 raw=json.dumps(result,ensure_ascii=False,indent=2).encode("utf-8")
 (out/(lane+".json")).write_bytes(raw)
 print(json.dumps({"lane":lane,"status":"READ_ONLY_VALIDATED","stage":group,"bytes":len(raw),"history_promotion":False},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
