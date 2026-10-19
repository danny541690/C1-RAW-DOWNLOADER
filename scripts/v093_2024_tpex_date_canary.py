"""2024 TPEx historical endpoint safety canary. No Drive writing.
Test exact dates with current URL scheme and ROC slash variant. Never claim valid unless response date matches.
"""
import json,urllib.request,urllib.parse,hashlib,time
from scripts.v093_2024_integrity_r2 import actual_date
CASES=["2024-04-01","2024-04-02","2024-05-07"]
def main():
 for target in CASES:
  y,m,d=map(int,target.split("-"))
  for kind,dt in (("gregorian_compact",f"{y}{m:02d}{d:02d}"),("roc_slash",f"{y-1911}/{m:02d}/{d:02d}"),("gregorian_slash",f"{y}/{m:02d}/{d:02d}")):
   url="https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?"+urllib.parse.urlencode({"date":dt,"response":"json"})
   out={"target":target,"query_format":kind,"parameter":dt}
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-v093-integrity-canary"}),timeout=20) as r:raw=r.read(7000000)
    obj=json.loads(raw.decode("utf-8-sig"))
    out.update({"response_date":actual_date(obj),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"status":"DATE_MATCH" if actual_date(obj)==target else "DATE_MISMATCH_OR_UNKNOWN"})
   except Exception as e:out.update({"status":"FETCH_ERROR","error":type(e).__name__+":"+str(e)[:130]})
   print(json.dumps(out,ensure_ascii=False),flush=True)
   time.sleep(1)
if __name__=="__main__":main()
