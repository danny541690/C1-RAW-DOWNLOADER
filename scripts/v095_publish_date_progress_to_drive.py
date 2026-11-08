#!/usr/bin/env python3
"""Publish six-source JARVIS v0.95 DATE-based progress, based on real Drive cursors.

A cursor offset means "inspected through", NEVER all dates verified. Archive
months mean "source month has some immutable candidates", NEVER full month.
Actual release timestamps, history completeness and PIT remain separate.
"""
import csv,datetime as dt,hashlib,json,os,pathlib,re
from scripts.v095_market_release_calendar_drive_archive import drive,archive,OPS
from scripts.v095_2026_annual_consolidated import BRONZE_ROOTS
from scripts.v095_2026_four_source_archive_intake import ls
OUT=pathlib.Path("v095_schedule_date_progress")
TODAY=min(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date(),dt.date(2026,12,31))
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
def sha(b):return hashlib.sha256(b).hexdigest()
def weekdays():
    d=dt.date(2026,1,1);r=[]
    while d<=TODAY:
        if d.weekday()<5:r.append(d.isoformat())
        d+=dt.timedelta(days=1)
    return r
def remote_files(d,parent,contains):
    q="'"+parent+"' in parents and name contains '"+contains+"' and trashed=false"
    found=[];token=None
    while True:
        x=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,createdTime,mimeType)",pageSize=1000,pageToken=token).execute()
        if x.get("incompleteSearch"):raise RuntimeError("INCOMPLETE_DRIVE_CHECKPOINT_SEARCH")
        found.extend(x.get("files",[]));token=x.get("nextPageToken")
        if not token:break
    return found
def latest_cursor(d,source,days):
    prefix="JARVIS_V095_2026_PRICE_CURSOR_"+source+"_"
    match=re.compile(re.escape(prefix)+r"(\d+)_\d+_([a-f0-9]{16})\.json")
    choices=[]
    for f in remote_files(d,OPS,prefix):
        m=match.fullmatch(f["name"])
        if m:choices.append((int(m[1]),f,m[2]))
    if not choices:raise ValueError("NO_DURABLE_PRICE_CURSOR_"+source)
    choices.sort(key=lambda x:x[0],reverse=True)
    gen,f,digestprefix=choices[0]
    raw=d.files().get_media(fileId=f["id"]).execute()
    if sha(raw)[:16]!=digestprefix:raise ValueError("CURSOR_SHA_MISMATCH_"+source)
    c=json.loads(raw)
    if c.get("generation")!=gen or c.get("offset",-1)>len(days):raise ValueError("CURSOR_GENERATION_OR_DATE_RANGE")
    i=c["offset"]
    return {
      "date_unit":"交易日（候選平日巡檢）","requested_from":"2026-01-01",
      "inspected_through":days[i-1] if i else None,
      "next_uninspected":days[i] if i<len(days) else None,
      "cursor_offset":i,"candidate_weekdays_through_today":len(days),
      "last_batch_failed_dates":[x.get("date") for x in c.get("failed_items",[]) if x.get("date")],
      "pending_retry_dates":[x.get("date") for x in c.get("retry_queue",[]) if x.get("date")],
      "last_batch_failed_count":c.get("failed_units"),
      "last_batch_success_count":c.get("success_units"),
      "checkpoint_run_id":c.get("run_id"),"cursor_generation":gen,
      "cursor_sha256":sha(raw),
      "date_progress_semantics":"INSPECTED_NOT_FULLY_VERIFIED",
      "whole_period_complete":False,"pit_verified":False
    }
def legacy_candidates(d,source):
    root=BRONZE_ROOTS[source]
    folders=remote_files(d,root,"_V093_REUSE_CANDIDATE")
    months=[];total=0
    for f in folders:
        m=re.fullmatch(r"(2026-\d{2})_V093_REUSE_CANDIDATE",f["name"])
        if not m or f.get("mimeType")!="application/vnd.google-apps.folder":continue
        children=remote_files(d,f["id"],"V095_V093_"+source+"_")
        valid=[x for x in children if re.fullmatch(r"V095_V093_"+source+r"_2026-\d{2}_[a-f0-9]{24}\.zip",x["name"])]
        if valid:
            months.append(m[1]);total+=len(valid)
    months=sorted(set(months))
    return {"candidate_months":months,"candidate_files_observed":total,
       "candidate_month_start":months[0] if months else None,
       "candidate_month_end":months[-1] if months else None,
       "date_progress_semantics":"SOME_CANDIDATE_ARCHIVES_EXIST_NOT_COMPLETE_MONTH",
       "whole_period_complete":False,"pit_verified":False}
def ndc_from_verified_archive(d):
    prefix="JARVIS_V095_G0_2000_2026_ndc_monthly_manifest_"
    matches=[]
    for f in remote_files(d,OPS,prefix):
        m=re.fullmatch(re.escape(prefix)+r"([a-f0-9]{24})\.json",f["name"])
        if m:matches.append((f,m[1]))
    if not matches:raise ValueError("NO_NDC_MONTH_RECEIPT")
    vals=[]
    for f,abbrev in matches:
        raw=d.files().get_media(fileId=f["id"]).execute()
        if sha(raw)[:24]!=abbrev:raise ValueError("NDC_MANIFEST_REMOTE_SHA_MISMATCH")
        r=json.loads(raw);vals.append((r["month_rows"],r["monthly_observation_last"],raw,r))
    vals.sort(key=lambda x:(x[1],x[0]),reverse=True)
    _,_,raw,m=vals[0]
    return {"date_unit":"觀察月份（非公布日期）",
      "observation_start":m["monthly_observation_first"],
      "observation_end":m["monthly_observation_last"],
      "observed_month_count":m["month_rows"],
      "native_indicator_series":m.get("native_indicator_series"),
      "receipt_sha256":sha(raw),"date_progress_semantics":"REVISED_OBSERVATION_MONTH_NOT_PIT_RELEASE",
      "whole_period_complete":False,"pit_verified":False}
def tdcc_reference(d):
    prefix="JARVIS_V095_G0_2000_2026_tdcc_week_receipt_audit_"
    matches=[]
    for f in remote_files(d,OPS,prefix):
        m=re.fullmatch(re.escape(prefix)+r"([a-f0-9]{24})\.json",f["name"])
        if m:matches.append((f,m[1]))
    if not matches:return {"verified_reference_dates":None,"note":"歷史週次收據尚未從 Drive 找到合格可讀的管理檔"}
    vals=[]
    for f,h in matches:
        raw=d.files().get_media(fileId=f["id"]).execute()
        if sha(raw)[:24]!=h:raise ValueError("TDCC_WEEK_RECEIPT_SHA")
        r=json.loads(raw);vals.append((r.get("unique_positive_source_reference_dates",0),raw,r))
    vals.sort(key=lambda x:x[0],reverse=True)
    return {"verified_reference_dates":vals[0][0],
       "reference_date_scope":"2008-07 至 2026-11-08，稀疏正向證據",
       "week_receipt_sha256":sha(vals[0][1]),
       "note":"僅是有收據的週資料基準日，不代表所有歷史週次或公布日完整"}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=drive();dates=weekdays()
    per={}
    for source in ("TWSE","TPEx"):
        per[source]=latest_cursor(d,source,dates)
    for source in ("MOPS","TDCC","TAIFEX"):
        per[source]={"date_unit":"候選原始檔所屬月份（非完整月覆蓋）",**legacy_candidates(d,source)}
    per["TDCC"].update(tdcc_reference(d))
    per["NDC"]=ndc_from_verified_archive(d)
    statuses={
      "TWSE":"INCREMENTAL_DAY_CURSOR_ACTIVE",
      "TPEx":"INCREMENTAL_DAY_CURSOR_ACTIVE",
      "MOPS":"MONTHLY_NATIVE_CANDIDATES_NOT_PIT",
      "TDCC":"SPARSE_WEEK_REFERENCE_AND_MONTHLY_CANDIDATES",
      "TAIFEX":"SOURCE_MONTHS_AND_FORMAT_QUARANTINE",
      "NDC":"HISTORICAL_OBSERVATION_MONTHS_REUSED"
    }
    for s in SOURCES:per[s]["status"]=statuses[s]
    payload={"schema":"JARVIS_V095_SIX_SOURCE_DATE_PROGRESS_V1",
       "snapshot_date":TODAY.isoformat(),"source_workflow_run_id":"42458778942",
       "cursor_source":"LATEST_DURABLE_SHA_CHECKED_GOOGLE_DRIVE_RECEIPTS",
       "timezone":"Asia/Taipei",
       "sources":per,
       "no_fake_gaps":True,"historical_publication_date_complete":False,
       "all_six_sources_complete":False,"PIT_RELEASE_APPROVED":False}
    jsonpath=OUT/"JARVIS_V095_DATE_PROGRESS_20261108.json"
    jsonpath.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    csvpath=OUT/"JARVIS_V095_DATE_PROGRESS_20261108.csv"
    with csvpath.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["來源","日期單位","已巡檢至","下一待巡檢日","候選來源月份起","候選來源月份迄","候選月份清單","週基準日正向收據數","觀察月起","觀察月迄","觀察月數","最新失敗日期","待重試日期","狀態","完成認證"])
        for s in SOURCES:
            r=per[s]
            writer.writerow([s,r.get("date_unit"),r.get("inspected_through",""),r.get("next_uninspected",""),
               r.get("candidate_month_start",""),r.get("candidate_month_end",""),
               ";".join(r.get("candidate_months",[])),r.get("verified_reference_dates",""),
               r.get("observation_start",""),r.get("observation_end",""),r.get("observed_month_count",""),
               ";".join(r.get("last_batch_failed_dates",[])),";".join(r.get("pending_retry_dates",[])),
               r["status"],"NO"])
    md=["# JARVIS v0.95 六大來源日期進度（"+TODAY.isoformat()+"）","",
        "狀態為 GitHub/Google Drive Checkpoint 的日期證據，不是全量資料完整率。","",
        "|來源|已巡檢日期／已有資料月份|下一步日期／工作|備註|","|---|---|---|---|"]
    for s in SOURCES:
        r=per[s]
        progress=(r.get("inspected_through") or
          (", ".join(r.get("candidate_months",[])) if r.get("candidate_months") else
           r.get("observation_start","")+" ～ "+r.get("observation_end","")))
        nextstep=r.get("next_uninspected") or ("依該資料集發布週期核對未驗證來源日" if s!="NDC" else "補實際公布日及歷史 vintage")
        note=("最近批次失敗日："+",".join(r.get("last_batch_failed_dates",[])) if s in ("TWSE","TPEx") else
            ("已確認週基準日收據："+str(r.get("verified_reference_dates")) if s=="TDCC" else
             "部分月份存在候選檔，不代表全月完整"))
        md.append("|"+s+"|"+str(progress)+"|"+str(nextstep)+"|"+note+"|")
    md+=["","## 資料解讀規則",
         "- TWSE／TPEx 的游標只代表已巡檢平日清單，不能推斷日期以前都已通過原始數據驗證。",
         "- MOPS／TDCC／TAIFEX 的月份表示至少有一個候選封存檔，非該月全部資料已下載。",
         "- TDCC 週資料來源起點不同，週基準日與公布日不可混用。",
         "- NDC 觀察月份不等於資料初次公布時間；PIT 及 Gold 正式回測持續隔離。",
         "- 未來新排程應逐輪產出 completed_dates/failed_dates，並與官方應有日期交集計算來源覆蓋率。"]
    mdpath=OUT/"JARVIS_V095_DATE_PROGRESS_20261108.md"
    mdpath.write_text("\n".join(md)+"\n",encoding="utf-8")
    receipts=[archive(d,x) for x in (csvpath,jsonpath,mdpath)]
    result={"state":"DRIVE_SHA_READBACK_PASS","snapshot_date":TODAY.isoformat(),
       "run_id":os.getenv("GITHUB_RUN_ID"),"files":receipts,
       "market_day_progress":{s:{"inspected":per[s]["inspected_through"],
         "next":per[s]["next_uninspected"],
         "last_failed_dates":per[s]["last_batch_failed_dates"]} for s in ("TWSE","TPEx")},
       "legacy_months":{s:per[s].get("candidate_months") for s in ("MOPS","TDCC","TAIFEX")},
       "ndc_observations":per["NDC"]["observed_month_count"],
       "period_complete":False}
    (OUT/"date_progress_drive_receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
