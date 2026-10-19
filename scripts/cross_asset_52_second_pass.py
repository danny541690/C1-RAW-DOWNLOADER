"""Second-pass source discovery for 52 missing cross-asset indicators (2026-09).
Preserves the 20 successful source files; no proxies mislabeled as exact indices.
"""
import csv,datetime,hashlib,io,json,os,time,urllib.parse,urllib.request
from scripts.annual_actual_firstpass import Drive,service
from scripts.cross_asset_72_pilot import check,get,putjson
CONFIG="config/cross_asset_72_pilot_2026_09.json"
START="2026-09-01";END="2026-09-30"
# Candidate IDs must be independently validated for exact economic meaning.
FRED_CANDIDATES={
"FEDFUNDS":[("DFF","exact")],
"RUSSELL2000":[("RU2000PR","exact")],
"KOSPI":[("KOSPI","exact")],
"US_ISM":[("NAPM","exact")],
"COPPER":[("PCOPPUSDM","exact")],
"ALUMINUM":[("PALUMUSDM","exact")],
"NICKEL":[("PNICKUSDM","exact")],
"ZINC":[("PZINCUSDM","exact")],
"IRON_ORE":[("PIORECRUSDM","exact")],
"COTTON":[("PCOTTINDUSDM","exact")],
"SOYBEANS":[("PSOYBUSDM","exact")],
"CORN":[("PMAIZMTUSDM","exact")],
"WHEAT":[("PWHEAMTUSDM","exact")],
"US_NEW_ORDERS":[("AMTMNO","exact")],
"WOOD_PULP":[("WPU0911","candidate_needs_semantic_review")],
}
# Source-discovery entries: official free resource identified, but not yet a
# verified machine-readable exact-series URL. Never count as successful data.
DISCOVERY={
"TW_EXPORT_ORDERS_YOY":"https://data.gov.tw/en/datasets/6845",
"TW_EXPORT_YOY":"https://data.gov.tw/en/datasets/8378",
"TW_ELECTRONICS":"https://www.twse.com.tw/",
"TW_SEMI":"https://www.twse.com.tw/",
"GLOBAL_SEMI_SALES":"https://www.semiconductors.org/",
"SCFI":"https://en.sse.net.cn/indices/scfinew.jsp",
"CCFI":"https://en.sse.net.cn/indices/ccfinew.jsp",
"SCFIS_EU":"https://en.sse.net.cn/",
"BDI":"https://www.balticexchange.com/",
"BCI":"https://www.balticexchange.com/",
"BPI":"https://www.balticexchange.com/",
"BSI":"https://www.balticexchange.com/",
}
def fred_url(series):
 return "https://fred.stlouisfed.org/graph/fredgraph.csv?"+urllib.parse.urlencode({"id":series,"cosd":START,"coed":END})
def validate_fred(raw):
 records=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
 if not records or len(records[0])<2:raise ValueError("BAD_CSV")
 cols=[k for k in records[0] if k not in ("DATE","observation_date")]
 valid=[r for r in records if START<=str(r.get("DATE",r.get("observation_date","")))<=END and any(r.get(c) not in ("",".",None) for c in cols)]
 if not valid:raise ValueError("NO_NUMERIC_ROWS_IN_PERIOD")
 return len(valid)
def main():
 cfg=json.load(open(CONFIG,encoding="utf-8"))
 d=Drive(service());month=cfg["drive_folder_id"]
 dirs={s:d.folder(month,s) for s in ["FinMind","FRED","TWSE","TPEx","MOPS","TAIFEX","OTHER_OFFICIAL","QA_REPORTS"]}
 cp=d.folder(dirs["QA_REPORTS"],"_CHECKPOINTS_V2")
 results=[]
 for x in cfg["indicators"]:
  ident=x["id"]
  # A persisted original success is never overwritten or retried.
  old=d.read(d.folder(dirs["QA_REPORTS"],"_CHECKPOINTS"),ident+".json")
  oldobj=json.loads(old) if old else {}
  if oldobj.get("status")=="SAVED_BASIC_VALID":continue
  old2=d.read(cp,ident+".json");state=json.loads(old2) if old2 else {}
  if state.get("status")=="SAVED_BASIC_VALID":
   results.append(state);continue
  candidate=FRED_CANDIDATES.get(ident,[])
  status="SOURCE_DISCOVERY_REQUIRED";err="";rows=0;total=0;sha=None;source_url=None;quality="NOT_VERIFIED";selected=None
  # One request per candidate, cumulative max 4; no repeated 404 hammering.
  attempts=int(state.get("attempts",0))
  for series,semantic in candidate:
   if attempts>=4:break
   url=fred_url(series);source_url=url
   filename=ident+"_"+series+"_V2.csv"
   raw=d.read(dirs["FRED"],filename)
   if raw is None:
    attempts+=1
    putjson(d,cp,ident+".json",{"id":ident,"status":"IN_PROGRESS","attempts":attempts,"source_url":url})
    try:raw=get(url)
    except Exception as e:
     err=type(e).__name__+":"+str(e)[:140]
     status="SOURCE_HOLD" if "429" in err or "403" in err else "DEFERRED_MISSING"
     continue
   try:
    rows=validate_fred(raw)
    # A candidate requiring semantic review must not be called exact.
    status="SAVED_BASIC_VALID" if semantic=="exact" else "SAVED_SEMANTIC_REVIEW_REQUIRED"
    d.put(dirs["FRED"],filename,raw,"text/csv")
    total=len(raw);sha=hashlib.sha256(raw).hexdigest();quality="BASIC_ONLY" if semantic=="exact" else "SEMANTIC_UNVERIFIED";selected=series;err=""
    break
   except Exception as e:
    err=type(e).__name__+":"+str(e)[:140]
    status="NO_DATA_IN_MONTH" if "NO_NUMERIC" in err else "DEFERRED_MISSING"
  rec={"id":ident,"period":"2026-09","status":status,"rows":rows,"bytes":total,"sha256":sha,"attempts":attempts,"error":err,"source":"FRED" if candidate else "SOURCE_DISCOVERY","series":selected,"source_url":source_url,"candidate_reference":DISCOVERY.get(ident),"validation":quality,"PIT_verified":False}
  putjson(d,cp,ident+".json",rec);results.append(rec)
  print(json.dumps({"id":ident,"status":status,"rows":rows},ensure_ascii=False),flush=True)
 counts={s:sum(x["status"]==s for x in results) for s in sorted(set(x["status"] for x in results))}
 report={"period":"2026-09","stage":"SECOND_PASS","previous_success_count":20,"remaining_count":len(results),"counts":counts,"new_rows":sum(x["rows"] for x in results),"new_bytes":sum(x["bytes"] for x in results),"completed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"records":results}
 putjson(d,dirs["QA_REPORTS"],"2026-09_CROSS_ASSET_52_SECOND_PASS.json",report)
 print(json.dumps({"remaining":len(results),"counts":counts},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
