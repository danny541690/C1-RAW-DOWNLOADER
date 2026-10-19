"""Third pass: official Taiwan source endpoint smoke tests, source evidence only.
Does not count a fetched webpage as a valid economic indicator.
"""
import datetime,hashlib,json,urllib.parse,urllib.request
from scripts.annual_actual_firstpass import Drive,service
from scripts.cross_asset_72_pilot import putjson
MONTH="2026-09"
TARGETS={
 "TWSE_FMTQIK_202609":"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=20260901",
 "TWSE_FMI_INDEX_202609":"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date=20260901",
 "TWSE_MI_INDEX_20260930":"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=20260930&type=ALL",
 "TAIFEX_FUTURES_DAILY":"https://www.taifex.com.tw/cht/3/futDailyMarketView",
 "TAIFEX_FUTURES_REPORT":"https://www.taifex.com.tw/cht/3/futDailyMarketReport",
 "SCFI_OFFICIAL":"https://en.sse.net.cn/indices/scfinew.jsp",
 "CCFI_OFFICIAL":"https://en.sse.net.cn/indices/ccfinew.jsp",
 "BDI_OFFICIAL":"https://www.balticexchange.com/",
 "SIA_GLOBAL_SEMI":"https://www.semiconductors.org/",
 "TW_GOV_OPEN_DATA":"https://data.gov.tw/",
}
def main():
 d=Drive(service());folder="1yCThJ7FAfjfMyjDLte1jREHVINFROnRM"
 qa=d.folder(folder,"QA_REPORTS");raw=d.folder(folder,"OTHER_OFFICIAL")
 results=[]
 for name,url in TARGETS.items():
  rec={"name":name,"url":url,"status":"NOT_TESTED","bytes":0,"sha256":None,"indicator_validated":False,"period_validated":False}
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; JARVIS-C1-v093-source-audit)","Accept":"application/json,text/html,*/*"})
   with urllib.request.urlopen(req,timeout=25) as resp:
    body=resp.read(1500001);ct=resp.headers.get("Content-Type","")
    rec.update(http_status=resp.status,content_type=ct,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
   if len(body)>1500000:raise ValueError("BODY_TOO_LARGE")
   if "json" in ct or body.lstrip().startswith((b"{",b"[")):
    try:
     obj=json.loads(body.decode("utf-8-sig"))
     rec["json_keys"]=list(obj.keys())[:15] if isinstance(obj,dict) else []
     rec["status"]="JSON_RETRIEVED_UNVERIFIED"
    except Exception as e:rec["status"]="BAD_JSON";rec["error"]=str(e)[:160]
   else:rec["status"]="PAGE_RETRIEVED_NOT_DATA"
   ext=".json" if rec["status"]=="JSON_RETRIEVED_UNVERIFIED" else ".html"
   d.put(raw,name+"_source_response"+ext,body,"application/json" if ext==".json" else "text/html",overwrite=True)
  except Exception as e:rec["status"]="FETCH_FAILED";rec["error"]=type(e).__name__+":"+str(e)[:180]
  results.append(rec)
  putjson(d,qa,"SOURCE_TEST_"+name+".json",rec)
  print(json.dumps({"name":name,"status":rec["status"]},ensure_ascii=False),flush=True)
 report={"stage":"THIRD_PASS_SOURCE_AUDIT","period":MONTH,"source_checks":len(results),"validated_indicators_added":0,"notes":"Source responses are isolated from indicator data; must parse and cross-check economic series before promotion.","results":results,"timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 putjson(d,qa,"2026-09_CROSS_ASSET_THIRD_PASS_SOURCE_AUDIT.json",report)
if __name__=="__main__":main()
