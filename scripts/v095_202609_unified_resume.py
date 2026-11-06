"""One GitHub job; reuse existing September Bronze/Silver/Gold, rerun only missing partitions.
Do not turn an unsupported indicator or an old unvalidated archive into a released feature.
"""
import os,json,pathlib,subprocess,sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
OUT=pathlib.Path("v095_unified_202609");OUT.mkdir(exist_ok=True)
# These IDs are from known good September QA receipts; IDs remain stable across runs.
ARTIFACTS={
 "Silver/TSE_OHLCV":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz",
 "Silver/OTC_OHLCV":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk",
 "Silver/MOPS_Revenue":"1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5",
 "Silver/TDCC_Weekly":"1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r",
 "Gold/TSE_Price":"1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI",
 "Gold/OTC_Price":"1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6",
 "Gold/MOPS_Revenue":"1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI",
 "Gold/TSE_Flow":"18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7",
 "Gold/OTC_Margin":"11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5"
}
# Fallback jobs may have existing immutable outputs, so avoid automatic destructive writes.
REPAIR={
 "Silver/TSE_OHLCV":["scripts/v095_202609_silver_ohlcv_candidate.py"],
 "Silver/OTC_OHLCV":["scripts/v095_202609_silver_ohlcv_candidate.py"],
 "Silver/MOPS_Revenue":["scripts/v095_202609_mops_silver_revenue_candidate.py"],
 "Silver/TDCC_Weekly":["scripts/v095_202609_tdcc_silver_candidate.py"]
}
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());d=build("drive","v3",credentials=c,cache_discovery=False)
 summary={"month":"2026-09","schema":"JARVIS_V095_UNIFIED_RESUME_RECEIPT",
 "source_priority":["V093","SIX_OFFICIAL","FINMIND_FREE"],"checked":{},"executed_repairs":[],
 "full_443_pit_ready":False}
 for label,id in ARTIFACTS.items():
  try:
   f=d.files().get(fileId=id,fields="id,name,size,trashed").execute()
   if f.get("trashed"):raise ValueError("FILE_TRASHED")
   summary["checked"][label]={"status":"EXISTS","id":id,"bytes":int(f.get("size") or 0)}
  except Exception as e:
   summary["checked"][label]={"status":"NEEDS_REVALIDATION","id":id,"error":type(e).__name__}
   # The old creators also use immutable same-name output. They are safe to retry only if
   # source + target QA can be reconciled; metadata errors do not prove source absent.
   summary["checked"][label]["automatic_repair"]="BLOCKED_SOURCE_VS_TARGET_RECONCILIATION"
 # Silver and Gold candidate files are checked but not overwritten based on mere metadata.
 # For confirmed missing source/date units, a dataset-specific source contract is required.
 (OUT/"resume_manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps({"checked":len(summary["checked"]),"exist":sum(x["status"]=="EXISTS" for x in summary["checked"].values()),"auto_repair":"NONE_IF_UNCERTAIN"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
