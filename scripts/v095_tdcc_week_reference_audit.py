#!/usr/bin/env python3
"""Read-only audit of existing TDCC official historical weekly date receipts.

Never synthesize dates from Fridays, never infer annual completeness from a
partial distribution-code sample. Count a date as positive source evidence only
when previously stored receipt has file_id, SHA and verified remote readback.
PIT publication timestamps remain unknown.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib,re
from scripts.v095_market_release_calendar_drive_archive import drive,archive
from scripts.v093_tdcc_independent import REPORT
OUT=pathlib.Path("v095_tdcc_week_inventory")
FOLDERS=("TDCC_INDEPENDENT_STAGE05","TDCC_INDEPENDENT_STAGE05_ASC")
MAX_HISTORY_FILES=150
def history_files(d,parent):
    q="'"+parent+"' in parents and name contains 'HISTORY_' and trashed=false"
    items=[];token=None
    while True:
        r=d.files().list(q=q,pageSize=500,fields="nextPageToken,incompleteSearch,files(id,name,size)",pageToken=token).execute()
        if r.get("incompleteSearch"):raise ValueError("TDCC_HISTORY_LIST_INCOMPLETE")
        items += [x for x in r.get("files",[]) if re.fullmatch(r"HISTORY_\\d{8}\\.json",x["name"])]
        if len(items)>2000:raise ValueError("TDCC_HISTORY_MANIFEST_OVER_BOUNDED_LIMIT")
        token=r.get("nextPageToken")
        if not token:break
    return sorted(items,key=lambda x:x["name"],reverse=True)

def sha(b):return hashlib.sha256(b).hexdigest()
def ls(d,parent,name):
    q="'"+parent+"' in parents and name = '"+name+"' and trashed=false"
    items=[];token=None
    while True:
        r=d.files().list(q=q,pageSize=100,fields="nextPageToken,incompleteSearch,files(id,name,mimeType)",pageToken=token).execute()
        if r.get("incompleteSearch"):raise ValueError("TDCC_DRIVE_LIST_INCOMPLETE")
        items+=r.get("files",[]);token=r.get("nextPageToken")
        if not token:break
    if len(items)>1:raise ValueError("DUPLICATE_TDCC_FILE_OR_FOLDER_"+name)
    return items[0]["id"] if items else None
def read(d,parent,name):
    f=ls(d,parent,name)
    return d.files().get_media(fileId=f).execute() if f else None
def is_saved(x):
    return (x.get("status")=="SAVED_BASIC_VERIFIED" and x.get("file_id")
            and re.fullmatch(r"[a-f0-9]{64}",str(x.get("sha256","")))
            and x.get("remote_readback_hash_verified") is True)
def main():
    OUT.mkdir(exist_ok=True)
    d=drive();dates=collections.defaultdict(list);errors=[];directories=[];scanned=0
    for label in FOLDERS:
        directory=ls(d,REPORT,label)
        if not directory:
            directories.append({"folder":label,"status":"NO_PRIOR_CAPTURE_DIRECTORY"})
            continue
        snapshot=read(d,directory,"CURSOR.json")
        if not snapshot:
            directories.append({"folder":label,"status":"NO_PRIOR_CURSOR"})
            continue
        cursor=json.loads(snapshot)
        ledger=cursor.get("history_receipts",{})
        receiptdate=cursor.get("history_receipt_date")
        if receiptdate:
            raw=read(d,directory,"HISTORY_"+receiptdate+".json")
            if raw:ledger=json.loads(raw)
        history=history_files(d,directory)
        ledgers=[(receiptdate or "CURSOR",ledger)]
        for sourcefile in history[:MAX_HISTORY_FILES]:
            item=json.loads(d.files().get_media(fileId=sourcefile["id"]).execute())
            if not isinstance(item,dict):raise ValueError("TDCC_HISTORY_FILE_NOT_LEDGER")
            ledgers.append((sourcefile["name"],item))
        good=0
        seen=set()
        for ledger_file,ledger in ledgers:
          for key,record in ledger.items():
            if (key,str(record.get("file_id"))) in seen:continue
            seen.add((key,str(record.get("file_id"))))
            scanned+=1
            if not is_saved(record):continue
            m=re.fullmatch(r"(20\d{2})(\d{2})(\d{2})\|([0-9A-Za-z]+)",key)
            if not m:
                errors.append({"folder":label,"problem":"VERIFIED_RECEIPT_NONSTANDARD_DATE_KEY","hash":sha(key.encode())[:16]})
                continue
            year,month,day=map(int,m.groups()[:3])
            try:date=dt.date(year,month,day)
            except ValueError:continue
            if not dt.date(2008,7,1)<=date<=dt.date(2026,11,8):continue
            dates[date.isoformat()].append({"stock":m[4],"sha256":record["sha256"],"file_id":record["file_id"]})
            good+=1
        directories.append({"folder":label,"status":"RECEIPTS_SCANNED","cursor_sha256":sha(snapshot),
                            "history_files_found":len(history),"history_files_read":min(len(history),MAX_HISTORY_FILES),
                            "history_files_remaining":max(0,len(history)-MAX_HISTORY_FILES),
                            "history_receipts_inspected":scanned,"fully_qualified_verified_receipts":good})
    out=OUT/"tdcc_positive_week_reference_dates.csv"
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["date","source","state","verified_security_receipts","publication_timestamp_verified"])
        for date,rec in sorted(dates.items()):
            w.writerow([date,"TDCC","DATE_IN_POSITIVE_SOURCE_RECEIPT",len(rec),"false"])
    report={"source":"TDCC","date_start":"2008-07","date_end":"2026-11-08",
      "unique_positive_source_reference_dates":len(dates),"receipts_inspected":scanned,
      "all_preexisting_history_manifests_read":all(x.get("history_files_remaining",0)==0 for x in directories),
      "directories":directories,"date_parse_errors":errors[:25],
      "source_date_vs_published_at_distinct":True,
      "weekly_full_universe_certified":False,"historical_published_at_PIT_certified":False,
      "data_before_2008_07_not_required":True,"csv_sha256":sha(out.read_bytes())}
    p=OUT/"tdcc_week_receipt_audit.json";p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    for item in (out,p):archive(d,item)
    print(json.dumps({"tdcc_confirmed_reference_dates":len(dates),
      "old_receipts_inspected":scanned,"dir_states":directories,
      "publication_PIT_complete":False},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
