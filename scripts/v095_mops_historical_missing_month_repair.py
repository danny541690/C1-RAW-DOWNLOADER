#!/usr/bin/env python3
"""Repair only failed MOPS historical monthly source URLs from prior G0 reports.

Each prior saved report is content-hash verified before reading. Only entries
previously UNVERIFIED are requested, with two historical filename variants and
two *official* hosts. Does not claim historical publication timestamp/PIT.
"""
import argparse,collections,csv,datetime as dt,hashlib,io,json,pathlib,re,urllib.error,zipfile
from scripts.v095_market_release_calendar_drive_archive import drive,archive,OPS
from scripts.v095_five_source_calendar_harvest import fetch,dated_evidence,sha
OUTPUT=pathlib.Path("v095_mops_date_repair")
PREFIX="JARVIS_V095_G0_2000_2026_"
def get_report(s,first,last):
    stem=f"mops_{first}_{last}_historical_evidence"
    prefix=PREFIX+stem+"_"
    q="'"+OPS+"' in parents and name contains '"+prefix+"' and trashed=false"
    files=[];token=None
    while True:
        x=s.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name)",
                         pageSize=1000,pageToken=token).execute()
        if x.get("incompleteSearch"):raise ValueError("DRIVE_INCOMPLETE_LIST")
        files+=x.get("files",[]);token=x.get("nextPageToken")
        if not token:break
    reports=[]
    for f in files:
        m=re.fullmatch(re.escape(prefix)+r"([a-f0-9]{24})\.json",f["name"])
        if not m:continue
        b=s.files().get_media(fileId=f["id"]).execute()
        if sha(b)[:24]!=m[1]:raise ValueError("SOURCE_REPORT_REMOTE_SHA_MISMATCH")
        doc=json.loads(b)
        if doc.get("source")=="MOPS" and doc.get("year_start")==first and doc.get("year_end")==last:
            reports.append(doc)
    if not reports:raise ValueError("PRIOR_MOPS_SHARD_REPORT_MISSING")
    reports.sort(key=lambda x:sum(z["state"]!="UNVERIFIED_NOT_MISSING" for z in x["source_rows"]),reverse=True)
    return reports[0]
def urls(year,month,board):
    roc=year-1911
    for host in ("mopsov.twse.com.tw","doc.twse.com.tw"):
        for suffix in ("","_0"):
            yield f"https://{host}/nas/t21/{board}/t21sc03_{roc}_{month}{suffix}.html"
def main(first,last):
    OUTPUT.mkdir(exist_ok=True)
    s=drive();prior=get_report(s,first,last)
    pending=[x for x in prior["source_rows"] if x["state"]=="UNVERIFIED_NOT_MISSING"]
    rescued=[];still=[];source_objects=[]
    for x in pending:
        detail={"year":x["year"],"month":x["month"],"board":x["category"],"previous_error":x.get("error","")}
        errors=[]
        for url in urls(x["year"],x["month"],x["category"]):
            try:
                raw,ctype=fetch(url)
                dates,tag=dated_evidence("MOPS",raw,x["year"],x["month"],x["category"])
                assert tag=="ARCHIVED_MONTHLY_REPORT_BYTES_ONLY_PIT_UNVERIFIED"
                digest=sha(raw)
                source_objects.append((f"{x['year']}_{x['month']:02d}_{x['category']}_{digest[:16]}.html",raw))
                rescued.append({**detail,"status":"MONTHLY_REPORT_PRESENT_NOT_PUBLICATION_TIMESTAMP",
                                "sha256":digest,"bytes":len(raw),"url":url})
                break
            except Exception as e:
                errors.append(type(e).__name__+":"+str(e)[:85])
        else:still.append({**detail,"status":"OFFICIAL_SOURCE_UNVERIFIED_NOT_MISSING",
                            "errors":errors})
    unique={}
    for name,raw in source_objects:unique[name]=raw
    archive_file=OUTPUT/f"mops_{first}_{last}_repaired_native.zip"
    with zipfile.ZipFile(archive_file,"w",zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(unique.items()):z.writestr(name,raw)
    report={"years":[first,last],"original_source_month_boards":len(prior["source_rows"]),
        "prior_verified":len(prior["source_rows"])-len(pending),
        "pending_repair":len(pending),"new_verified_month_boards":len(rescued),
        "still_unverified":len(still),"rescued":rescued,"unverified":still,
        "source_native_zip_sha256":sha(archive_file.read_bytes()),
        "PIT_release_timestamp_verified":False,"false_missing_declared":0}
    path=OUTPUT/f"mops_{first}_{last}_repair_receipt.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"years":[first,last],"previously_verified":report["prior_verified"],
      "new_verified":len(rescued),"still_unverified":len(still),
      "native_source_sha_readback_required":True},ensure_ascii=False),flush=True)
    d=drive()
    artifacts=[archive(d,p) for p in (archive_file,path)]
    print(json.dumps({"source":"MOPS","drive_sha_readback_verified":True,
                      "artifacts":len(artifacts)},ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True);p.add_argument("--end",type=int,required=True)
    a=p.parse_args();main(a.start,a.end)
