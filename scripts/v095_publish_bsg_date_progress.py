#!/usr/bin/env python3
"""JARVIS v0.95 dated Bronze/Silver/Gold progress. Source files are checked
by Drive filename inventory; presence never means full coverage or PIT."""
import csv,datetime as dt,hashlib,json,os,pathlib,re
from scripts.v095_publish_date_progress_to_drive import (drive,archive,remote_files,
    latest_cursor,legacy_candidates,ndc_from_verified_archive,tdcc_reference,weekdays,TODAY,OUT)
from scripts.v095_ultimate_r1_november_official import SOURCES as PRICE_SOURCES,GOLD
from scripts.v095_2026_cash_market_calendar import load_calendar
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
STAGES=("BRONZE","SILVER","GOLD")
def priced_stages(d,source,trade_days):
    cfg=PRICE_SOURCES[source]
    roots={"BRONZE":cfg["bronze"],"SILVER":cfg["silver"],"GOLD":GOLD}
    stages={}
    for stage,root in roots.items():
        folders=remote_files(d,root,"2026-")
        found=set()
        for folder in folders:
            name=folder["name"]
            if folder.get("mimeType")!="application/vnd.google-apps.folder":continue
            suffix={"BRONZE":"","SILVER":"_CANDIDATE","GOLD":"_DESCRIPTIVE_ONLY"}[stage]
            if not re.fullmatch(r"2026-\d{2}"+suffix,name):continue
            entries=remote_files(d,folder["id"],"V095_")
            for entry in entries:
                filename=entry["name"]
                mid={"BRONZE":"","SILVER":"_OHLCV","GOLD":"_PRICE_GOLD"}[stage]
                ext="json" if stage=="BRONZE" else "parquet"
                pattern=(r"V095_2026\d{2}_"+re.escape(source)
                  +r"_(2026-\d{2}-\d{2})"+mid+r"_[a-f0-9]{20}\."+ext)
                m=re.fullmatch(pattern,filename)
                if m and m[1][:7]==name[:7] and m[1]<=TODAY.isoformat():found.add(m[1])
        dates=sorted(found)
        confirmed_dates=set(dates)&trade_days
        stages[stage]={"first":dates[0] if dates else None,
           "last":dates[-1] if dates else None,"candidate_date_count":len(dates),
           "candidate_days":dates,
           "official_sessions_through_today":len(trade_days),
           "candidate_dates_on_official_sessions":len(confirmed_dates),
           "candidate_file_date_coverage_pct":round(100*len(confirmed_dates)/len(trade_days),1) if trade_days else None,
           "candidate_file_coverage_not_SHA_or_PIT_verified":True,
           "candidate_dates_not_matching_official_sessions":sorted(set(dates)-trade_days),
           "complete":False,"PIT":False,
           "label":("原始檔候選" if stage=="BRONZE" else
                    "格式轉換候選" if stage=="SILVER" else "描述性 Gold 候選（非 400+ 指標）")}
    return stages
def non_price_stages(d,source):
    if source=="NDC":
        v=ndc_from_verified_archive(d)
        first,last=v["observation_start"],v["observation_end"]
        label="官方修訂版 ZIP／觀察月份（非 PIT 初次發布）"
        candidate_count=v["observed_month_count"]
    else:
        v=legacy_candidates(d,source)
        first,last=v["candidate_month_start"],v["candidate_month_end"]
        label="來源原始 ZIP 候選（只證實有部分月檔）"
        candidate_count=v["candidate_files_observed"]
    return {"BRONZE":{"first":first,"last":last,"candidate_date_count":candidate_count,
             "complete":False,"PIT":False,"label":label},
       "SILVER":{"first":None,"last":None,"candidate_date_count":None,
             "complete":False,"PIT":False,"label":"尚無可確認的 dated typed Silver 正式驗收"},
       "GOLD":{"first":None,"last":None,"candidate_date_count":None,
             "complete":False,"PIT":False,"label":"尚無可確認的 400+ 指標 Gold／PIT 正式驗收"}}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=drive(); days=weekdays()
    calendar,_,_=load_calendar()
    trade_days={day for day,row in calendar.items() if day<=TODAY.isoformat() and row["TWSE_CASH"]=="TRADING"}
    records=[]
    for source in SOURCES:
        cursor=latest_cursor(d,source,days) if source in ("TWSE","TPEx") else {}
        stages=priced_stages(d,source,trade_days) if source in ("TWSE","TPEx") else non_price_stages(d,source)
        for stage in STAGES:
            item=stages[stage]
            records.append({"來源":source,"階層":stage,"建庫起始":"2000-01-01",
             "建庫目標結束":TODAY.isoformat(),
             "2026年度起始":"2026-01-01","2026年度結束":TODAY.isoformat(),
             "排程已巡檢至":cursor.get("inspected_through") or "",
             "下一待巡檢日":cursor.get("next_uninspected") or "",
             "階層最早候選日期":item["first"] or "未驗證",
             "階層最新候選日期":item["last"] or "未驗證",
             "有證據的日期／檔案數":item["candidate_date_count"] if item["candidate_date_count"] is not None else "",
             "官方應有交易日數":item.get("official_sessions_through_today",""),
             "候選檔日期覆蓋率%":item.get("candidate_file_date_coverage_pct",""),
             "巡檢平日候選進度%":round(100*cursor.get("cursor_offset",0)/len(days),1) if source in ("TWSE","TPEx") else "",
             "完整資料驗證進度%":"尚無可靠分母",
             "階層進度說明":item["label"],"歷史缺失日期":";".join(cursor.get("last_batch_failed_dates",[])),
             "全量完成":"否","PIT認證":"否"})
    day=TODAY.strftime("%Y%m%d")
    csvpath=OUT/("JARVIS_V095_BSG_DATE_PROGRESS_"+day+".csv")
    with csvpath.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    obj={"schema":"JARVIS_V095_SIX_SOURCE_BSG_DATE_PROGRESS_V1",
       "report_date":TODAY.isoformat(),"timezone":"Asia/Taipei",
       "history_start":"2000-01-01","history_target_end":TODAY.isoformat(),
       "yearly_start":"2026-01-01","yearly_end":TODAY.isoformat(),
       "rows":records,"all_sources_complete":False,"pit_verified":False,
       "coverage_interpretation":"Candidate file presence is not verified full data, production Gold or PIT",
       "meaning":"Drive candidate filenames date inventory; distinct from fully certified market coverage"}
    js=OUT/("JARVIS_V095_BSG_DATE_PROGRESS_"+day+".json")
    js.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=OUT/("JARVIS_V095_BSG_DATE_PROGRESS_"+day+".md")
    lines=["# JARVIS v0.95 六來源 Bronze／Silver／Gold 日期進度",
       "報告日："+TODAY.isoformat(),"建庫期間：2000-01-01 ～ "+TODAY.isoformat(),
       "2026 年度驗收期間：2026-01-01 ～ "+TODAY.isoformat(),"",
       "|來源|層級|起始|目標結束|目前候選進度|巡檢至|狀態|",
       "|---|---|---|---|---|---|---|"]
    for x in records:
        lines.append("|"+x["來源"]+"|"+x["階層"]+"|2026-01-01|"+TODAY.isoformat()+
           "|"+x["階層最早候選日期"]+" ～ "+x["階層最新候選日期"]+
           "|"+x["排程已巡檢至"]+"|"+x["階層進度說明"]+"|")
    lines+=["","註：巡檢至不代表此前全部成功；候選起訖日不代表日期連續完整。",
       "四來源無 typed Silver／Gold 日期驗證時不填入虛構進度。",
       "Gold 候選不代表 400+ 指標或 PIT 回測認證。",
       "TDCC 股權分散資料官方起點為 2008-07，不能當成 2000 起應有的缺漏。"]
    md.write_text("\n".join(lines)+"\n",encoding="utf-8")
    receipts=[archive(d,p) for p in (csvpath,js,md)]
    print(json.dumps({"status":"DRIVE_SHA_READBACK_PASS","run":os.getenv("GITHUB_RUN_ID"),
        "rows":len(records),"files":receipts,
        "summary":[{"source":s,"bronze":next(r for r in records if r["來源"]==s and r["階層"]=="BRONZE")["階層最新候選日期"],
                    "silver":next(r for r in records if r["來源"]==s and r["階層"]=="SILVER")["階層最新候選日期"],
                    "gold":next(r for r in records if r["來源"]==s and r["階層"]=="GOLD")["階層最新候選日期"],
                    "inspected_pct":next(r for r in records if r["來源"]==s and r["階層"]=="BRONZE")["巡檢平日候選進度%"],
                    "bronze_candidate_file_coverage_pct":next(r for r in records if r["來源"]==s and r["階層"]=="BRONZE")["候選檔日期覆蓋率%"],
                    "silver_candidate_file_coverage_pct":next(r for r in records if r["來源"]==s and r["階層"]=="SILVER")["候選檔日期覆蓋率%"],
                    "gold_candidate_file_coverage_pct":next(r for r in records if r["來源"]==s and r["階層"]=="GOLD")["候選檔日期覆蓋率%"]} for s in SOURCES]},ensure_ascii=False))
if __name__=="__main__":main()
