"""JARVIS C1 v0.95 Sep R3: bounded, evidence-aware scheduler.
A successful scheduler run is NOT a market-data or PIT certification.
Never resets existing data. Workflows are dispatched only for targeted gaps.
"""
import base64,datetime as dt,json,os,pathlib,time,urllib.error,urllib.parse,urllib.request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

REPO="danny541690/C1-RAW-DOWNLOADER"
BASE="https://api.github.com/repos/"+REPO
STATE="governance/v095/runtime/202609_R3_scheduler_state.json"
LEGACY="governance/v095/runtime/202609_autopilot_state.json"
POLICY="governance/v095/202609_scheduler_policy_R3.json"
TDCC_SRC="1_Pl4nN0HRXnIJSjJrt0iX2Lq7nkS1pcV"
CATALOG_ID="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
NATIVE="v095-tdcc-202609-native-bronze-migration.yml"
SILVER="v095-202609-silver-tdcc-conversion.yml"
GOLD="v095-202609-tdcc-gold-weekly.yml"

def gh(method,path,data=None):
    payload=json.dumps(data).encode() if data is not None else None
    request=urllib.request.Request(BASE+path,method=method,data=payload,
      headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],
        "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=35) as r:
        body=r.read()
        return json.loads(body) if body else {}
def file_read(path,default=None):
    try:
        d=gh("GET","/contents/"+path)
        return json.loads(base64.b64decode(d["content"]).decode()),d["sha"]
    except urllib.error.HTTPError as e:
        if e.code==404:return default,None
        raise
def save(s,sha):
    encoded=base64.b64encode((json.dumps(s,ensure_ascii=False,indent=2)+"\n").encode()).decode()
    data={"branch":"main","message":"checkpoint(v095): September R3 evidence-aware scheduler","content":encoded}
    if sha:data["sha"]=sha
    return gh("PUT","/contents/"+STATE,data)["content"]["sha"]
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def runs(workflow):
    encoded=urllib.parse.quote(workflow,safe="")
    return gh("GET","/actions/workflows/"+encoded+"/runs?per_page=10").get("workflow_runs",[])
def dispatch(workflow):
    gh("POST","/actions/workflows/"+urllib.parse.quote(workflow,safe="")+"/dispatches",{"ref":"main"})
    return stamp()
def creds():
    c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
      token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
      client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request())
    return build("drive","v3",credentials=c,cache_discovery=False)
def drive_observations():
    result={"status":"UNKNOWN","tdcc_native_copy_marker":False,"catalog_443_ids":False}
    for attempt in range(3):
        try:
            s=creds()
            listing=s.files().list(q="'"+TDCC_SRC+"' in parents and name = 'TDCC_202609_NATIVE_BRONZE_ORIGINAL_COPY_COMPLETE.json' and trashed = false",
                fields="files(id,name)",pageSize=5).execute().get("files",[])
            result["tdcc_native_copy_marker"]=len(listing)==1
            raw=s.files().get_media(fileId=CATALOG_ID).execute()
            catalog=json.loads(raw.decode("utf-8"))
            ids=catalog.get("indicators",[])
            result["catalog_443_ids"]=len(ids)==443 and len({v.get("id") for v in ids})==443
            result["catalog_all_443_formulas_certified"]=False
            result["status"]="OBSERVED"
            return result
        except (OSError,ConnectionError,TimeoutError) as e:
            result["error"]=type(e).__name__+":"+str(e)[:100]
            time.sleep((attempt+1)*2)
        except Exception as e:
            result["error"]=type(e).__name__+":"+str(e)[:180]
            break
    return result
def main():
    if os.environ.get("GITHUB_REPOSITORY")!=REPO:raise RuntimeError("WRONG_REPOSITORY")
    policy,_=file_read(POLICY)
    old,_=file_read(LEGACY)
    s,sha=file_read(STATE,{"schema":"JARVIS_V095_202609_R3_CONTROL",
        "period":"2026-09","previous_actions":[],"dispatch_counts":{},"created_utc":stamp()})
    if not policy or not old:raise RuntimeError("MISSING_INPUT_GOVERNANCE")
    flags,_=file_read("governance/v095/PHASE1_FLAGS.json")
    seen=drive_observations()
    steps=old.get("steps",{})
    bronze_jobs=[k for k in steps if "real-drive-byte-audit" in k or "bronze-admission" in k or "tpex-official-gap-recheck" in k or "seven-source-audit-bundle" in k]
    silver_jobs=[k for k in steps if "silver" in k and "gold" not in k]
    gold_jobs=[k for k in steps if ("gold" in k and k.startswith("v095")) or k=="v095-twse-credit-three-layer.yml"]
    s["evidence"]={"v093_to_v095_name_size":"41_OF_41_CANDIDATE_ONLY",
       "signed_dataset_contracts":bool(policy.get("signed_contracts",False)),
       "observed_bronze_runs_success":sum(steps[k].get("status")=="success" for k in bronze_jobs),
       "observed_silver_runs_success":sum(steps[k].get("status")=="success" for k in silver_jobs),
       "observed_gold_runs_success":sum(steps[k].get("status")=="success" for k in gold_jobs),
       "source_pit_verified":False,"all_443_formula_pit_verified":False,
       "catalog_443_ids":seen.get("catalog_443_ids",False),
       "tdcc_native_copy_marker":seen.get("tdcc_native_copy_marker",False),
       "drive_observation":seen.get("status")}
    if seen.get("error"):s["evidence"]["drive_error"]=seen["error"]
    s["candidate_scope"]="2026-09"
    s["source_order"]=policy["sources_priority"]
    s["pool_limits"]=policy["pools"]
    s["phase_status"]={"bronze":"CANDIDATE_ONLY","silver":"PARTIAL",
        "gold":"DESCRIPTIVE_SUBSETS_ONLY","pit":"BLOCKED","production":"BLOCKED"}
    s["release_approved"]=False
    s["action"]="MONITOR"
    # Native TDCC copies are separate immutable archives. Do not dispatch duplicate active runs.
    allruns={}
    for workflow in (NATIVE,SILVER,GOLD):allruns[workflow]=runs(workflow)
    tdcc=steps.get(SILVER,{})
    if tdcc.get("status")=="success":
        s["phase_status"]["silver"]="CANDIDATE_AWAITING_QA"
    else:
        s["phase_status"]["silver"]="PARTIAL_TDCC_PENDING"
    action=None
    if not seen.get("tdcc_native_copy_marker") and seen.get("status")=="OBSERVED":
        action=NATIVE
    elif tdcc.get("status")!="success" and seen.get("status")=="OBSERVED":
        action=SILVER
    if action:
        candidates=allruns[action]
        active=any(v.get("status") in ("queued","in_progress","pending","waiting","requested") for v in candidates[:5])
        prior=s["dispatch_counts"].get(action,0)
        if active:
            s["action"]="WAIT_ACTIVE:"+action
        elif action==SILVER and prior>=2:
            s["action"]="HOLD_RETRY_CAP:"+action
        elif action==NATIVE and prior>=policy.get("max_native_retries_per_day",4):
            s["action"]="HOLD_DAILY_BUDGET:"+action
        else:
            s["action"]="DISPATCH:"+action
            sent=dispatch(action)
            s["dispatch_counts"][action]=prior+1
            s["previous_actions"].append({"workflow":action,"sent_utc":sent,"reason":"MISSING_TDCC_NATIVE_PROOF" if action==NATIVE else "SILVER_TDCC_NOT_COMPLETE"})
    # If Silver becomes complete, a new Gold run still does not imply 443 PIT approval.
    s["quality_conclusion"]="BLOCKED_FORMULAS_PIT_SOURCE_UNIVERSE"
    s["updated_utc"]=stamp()
    # No extra GitHub commit if the state is unchanged except timestamp; avoid Actions flood.
    meaningful={k:v for k,v in s.items() if k!="updated_utc"}
    previous,_=file_read(STATE)
    if previous is None or {k:v for k,v in previous.items() if k!="updated_utc"}!=meaningful:
        sha=save(s,sha)
    out=pathlib.Path("v095_202609_R3")
    out.mkdir(exist_ok=True)
    (out/"report.json").write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"action":s["action"],"phase_status":s["phase_status"],
        "drive":seen,"dispatch_counts":s["dispatch_counts"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
