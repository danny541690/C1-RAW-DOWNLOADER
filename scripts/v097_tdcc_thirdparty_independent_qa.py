#!/usr/bin/env python3
"""Independent nonofficial TDCC archive provenance cross-check; never source authority.
Three actual same-date verified official TDCC cases. 17th holding level is total.
Record distinct MISSING_IN_ARCHIVE vs DIFFERENT vs EXACT. Preserve original SHA.
"""
import os,json,csv,io,hashlib,requests
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCE_REPO="wirelessr/tdcc-opendata-archive"
CASES=[("2026-09-18","YY0064",5241,97670909),
       ("2026-10-02","YFJ1",1,21000000),
       ("2026-10-16","YMM2",1,2400000)]
def main():
 r=[];cache={}
 for d,c,holders,shares in CASES:
  u="https://raw.githubusercontent.com/"+SOURCE_REPO+"/main/snapshots/2026/"+d+".csv"
  rec={"date":d,"code":c,"third_party_url":u,"official_proof_prior_run":"43370211117",
       "official_confirmed_holders":holders,"official_confirmed_shares":shares,
       "third_party_is_official":False}
  try:
   if d not in cache:
    response=requests.get(u,timeout=(10,45),headers={"User-Agent":"JARVIS-097-cross-source-audit"})
    response.raise_for_status()
    if len(response.content)>12_000_000:raise ValueError("OVER_SIZE")
    cache[d]=response.content
   b=cache[d]
   rec["third_party_snapshot_sha256"]=hashlib.sha256(b).hexdigest()
   entries=list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
   items=[row for row in entries if row.get("資料日期")==d.replace("-","") and row.get("證券代號","").strip()==c]
   rec["rows_for_code"]=len(items)
   level17=[x for x in items if x.get("持股分級")=="17"]
   if not items:rec["state"]="NONOFFICIAL_ARCHIVE_CODE_ABSENT_NOT_CORRUPTION"
   elif len(level17)!=1:rec["state"]="NONOFFICIAL_ARCHIVE_HOLDING_TOTAL_ABSENT"
   else:
    h=int(level17[0]["人數"]);s=int(level17[0]["股數"])
    rec.update(third_party_holders=h,third_party_shares=s,
        state="OFFICIAL_THIRDPARTY_AND_ORIGINAL_EXACT" if h==holders and s==shares else "THIRD_PARTY_DIFF_REVIEW")
  except Exception as e:rec.update(state="THIRD_PARTY_FETCH_OR_PARSE_HOLD",error=type(e).__name__+":"+str(e)[:155])
  r.append(rec)
 report={"schema":"v097_tdcc_independent_crosssource_1","run":RUN,
   "at":datetime.now(timezone.utc).isoformat(),"archive_provider":SOURCE_REPO,
   "official_source":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
   "result":r,"original_files_modified":False,"formal_bronze_admitted":0}
 api=service();_,_,q,_=common(api)
 put_once(api,q,"v097_TDCC_THIRD_PARTY_CROSSCHECK_"+RUN+".json",report)
 print("TDCC_THIRD_PARTY_CROSSCHECK="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
