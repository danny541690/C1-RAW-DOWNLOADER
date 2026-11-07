#!/usr/bin/env python3
"""R7 strict delta-only prelaunch checker.

Accepted scoped candidate receipts are never downloaded or rechecked here.
Only explicitly open issues are emitted into the actionable queue. A one-day
TWSE live source probe is read-only, not a new historical Bronze download.
"""
import argparse,datetime as dt,hashlib,json,pathlib,urllib.request,urllib.parse,urllib.error,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIPTS=ROOT/"governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json"
OUT=ROOT/"r7_problem_only"
def plan(data):
    accepted=data["immutable_receipts"];open_tasks=data["known_open_work"]
    keys=[x["key"] for x in accepted]
    ids=[x["id"] for x in open_tasks]
    assert len(keys)==len(set(keys)) and len(ids)==len(set(ids))
    assert len(accepted)==12 and len(open_tasks)==6
    assert not any(x.get("writes_allowed") for x in open_tasks)
    assert all(x["state"].startswith("PASS_") for x in accepted)
    assert data["limits"]["never_redownload_accepted"] and data["limits"]["never_recheck_accepted"]
    return {"schema":"JARVIS_V095_R7_DELTA_ONLY_V1","baseline_run_id":data["baseline_run_id"],
            "baseline_artifact_id":data["baseline_artifact_id"],
            "scope":"2026-09,2026-10,2026-11",
            "skipped_prior_candidate_count":len(accepted),"skipped_keys":keys,
            "open_issue_count":len(open_tasks),
            "actions":[{"id":x["id"],"action":x["action"],"source":x["source"],"period":x["month"],
                        "state":"OPEN","writes_allowed":False} for x in open_tasks],
            "download_count":0,"existing_files_rechecked":0,
            "production_release_approved":False,"historical_pit_certified":False}
def live_probe():
    date="20261106"
    url="https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?"+urllib.parse.urlencode({"date":date,"type":"ALLBUT0999","response":"json"})
    result={"source":"TWSE","date":"2026-11-06","target":"OFFICIAL_ENDPOINT_READ_ONLY","status":"NOT_ATTEMPTED",
            "bytes_read":0,"market_data_written":False,"attempts":0,"error_types":[]}
    for attempt in range(2):
        result["attempts"]=attempt+1
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-v095-R7-Diagnostic","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=12) as r:
                raw=r.read(4_000_001)
                if len(raw)>4_000_000:raise ValueError("OVER_LIMIT")
                if r.status!=200:raise ValueError("HTTP_NON_200")
            x=json.loads(raw)
            if not isinstance(x,dict) or x.get("stat") not in ("OK","ok"):
                raise ValueError("OFFICIAL_STATUS_NOT_OK")
            result.update(status="LIVE_HTTP_SAMPLE_PASS_NOT_FULL_DATASET",bytes_read=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            break
        except (ValueError,urllib.error.URLError,OSError,TimeoutError,json.JSONDecodeError) as exc:
            result["error_types"].append(type(exc).__name__)
            result["status"]="LIVE_HTTP_PROBE_BLOCKED"
            if attempt==0:time.sleep(2)
    return result
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("plan","probe"),default="plan")
    args=parser.parse_args()
    raw=json.loads(RECEIPTS.read_text())
    q=plan(raw)
    OUT.mkdir(parents=True,exist_ok=True)
    if args.mode=="probe":
        q["twse_live_probe"]=live_probe()
        q["actions"][0]["state"]=q["twse_live_probe"]["status"]
    q["count_open_remaining"]=sum(x["state"]!="PASS_FORMALLY_CERTIFIED" for x in q["actions"])
    (OUT/"report.json").write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:q[k] for k in ("baseline_run_id","skipped_prior_candidate_count","open_issue_count",
         "count_open_remaining","download_count","existing_files_rechecked")}|{"twse_probe":q.get("twse_live_probe")},ensure_ascii=False))
if __name__=="__main__":main()
