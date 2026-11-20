#!/usr/bin/env python3
"""R22 real remote GitHub contents optimistic-CAS *synthetic* test.
Only touches public .jarvis-test/v098_r22_remote_cas.json, no private IDs,
Drive, market data, Bronze, Silver or Gold. Multiple concurrent stale-SHA
updates must produce exactly one winner. Separate GitHub Run can replay with
the latest remote SHA. Does not implement a production lease by itself.
Second independent GitHub Run checks persisted remote generation and stale writes.
"""
import argparse,base64,concurrent.futures,json,os,pathlib,urllib.request,urllib.error
REPO="danny541690/C1-RAW-DOWNLOADER"
PATH=".jarvis-test/v098_r22_remote_cas.json"
URL=f"https://api.github.com/repos/{REPO}/contents/{PATH}"
TOKEN=os.environ.get("GITHUB_TOKEN")
def request(method,url,payload=None):
 if not TOKEN:raise RuntimeError("MISSING_GITHUB_TOKEN")
 body=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(url,data=body,method=method,headers={
  "Authorization":f"Bearer {TOKEN}","Accept":"application/vnd.github+json",
  "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JARVIS-R22-synthetic-CAS",
  "Content-Type":"application/json"})
 try:
  with urllib.request.urlopen(req,timeout=35) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:
  return e.code,{"status":"remote_http_error"}
def get():
 code,data=request("GET",URL)
 if code!=200:raise RuntimeError("REMOTE_CAS_STATE_UNREADABLE")
 info=json.loads(base64.b64decode(data["content"]).decode())
 if info.get("schema")!="JARVIS_R22_SYNTHETIC_REMOTE_CAS" or not info.get("test_only") or info.get("production_allowed"):
  raise RuntimeError("NOT_SYNTHETIC_STATE")
 return data["sha"],info
def put(sha,info,label):
 b64=base64.b64encode((json.dumps(info,sort_keys=True)+"\n").encode()).decode()
 return request("PUT",URL,{"message":"test(v098): synthetic R22 "+label,"content":b64,"sha":sha})
def attempt(args):
 sha,gen,label=args
 info={"schema":"JARVIS_R22_SYNTHETIC_REMOTE_CAS",
       "generation":gen,"owner":label,"test_only":True,"production_allowed":False}
 status,_=put(sha,info,label)
 return status
def main(path):
 initial_sha,initial=get()
 epoch=initial["generation"]
 actors=[f"R22_{os.environ.get('GITHUB_RUN_ID','manual')}_{i}" for i in range(8)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  results=list(pool.map(attempt,[(initial_sha,epoch+1,a) for a in actors]))
 winners=sum(c in (200,201) for c in results)
 conflicts=sum(c in (409,422) for c in results)
 if winners!=1 or conflicts!=7:raise RuntimeError(f"REMOTE_CONCURRENT_CAS_FAILURE_winners_{winners}_conflicts_{conflicts}")
 latest_sha,latest=get()
 if latest["generation"]!=epoch+1 or latest["owner"] not in actors:
  raise RuntimeError("REMOTE_GENERATION_NOT_MONOTONIC")
 stale_code=attempt((initial_sha,epoch+2,"STALE_WORKER"))
 if stale_code not in (409,422):raise RuntimeError("STALE_WORKER_OVERWROTE_CAS")
 # Sequential takeover with latest SHA; stale predecessor cannot ever commit.
 takeover_code=attempt((latest_sha,epoch+2,"R22_RECOVERY_"+os.environ.get("GITHUB_RUN_ID","manual")))
 if takeover_code not in (200,201):raise RuntimeError("RECOVERY_GENERATION_COMMIT_FAILED")
 _,final=get()
 if final["generation"]!=epoch+2 or not final["owner"].startswith("R22_RECOVERY_"):
  raise RuntimeError("RECOVERY_GENERATION_READBACK_FAILED")
 result={"status":"PASS_REMOTE_GITHUB_OPTIMISTIC_CAS_SYNTHETIC",
   "contenders":8,"successful_claims":winners,"remote_sha_conflicts":conflicts,
   "stale_generation_rejected":True,"new_generation_read_back":True,
   "initial_generation":epoch,"final_generation":final["generation"],
   "run_id":os.environ.get("GITHUB_RUN_ID"),"public_synthetic_only":True,
   "production_lease_expiry_certified":False,
   "all_production_workers_restricted_to_single_writer":False,
   "bulk_migration_allowed":False}
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,indent=2))
 print(json.dumps(result))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",required=True)
 main(p.parse_args().out)
