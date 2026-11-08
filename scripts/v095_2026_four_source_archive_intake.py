#!/usr/bin/env python3
"""Safe four-source 2026 archived Bronze candidate intake.

v0.93 first: copy only original native ZIP archives after SHA/CRC and source/month
manifest verification into isolated v0.95 staging folders. Never promote archive
CRC as verified financial contents or manufacture Silver/Gold/PIT. Missing
eligible files are reported for dedicated official-source backfill adapters.
"""
import datetime as dt
import calendar, csv, re, decimal
import hashlib, io, json, os, pathlib, sys, zipfile
from scripts.v095_2026_annual_consolidated import service,BRONZE_ROOTS,FOLDER
from scripts.v095_2026_prior_raw_reuse_audit import YEAR_PARENT
from scripts.v095_ultimate_r1_november_official import folder,save
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
MAX_SOURCE_FILES=min(int(os.environ.get("V095_ARCHIVE_BATCH","3")),6)
MAX_BYTES=20_000_000
MAX_INSPECT_PER_RUN=300

def ls(d,folder):
    rows=[];token=None
    while True:
        result=d.files().list(q="'"+folder+"' in parents and trashed=false",
          fields="nextPageToken,incompleteSearch,files(id,name,size,mimeType,md5Checksum)",pageSize=500,pageToken=token).execute()
        if result.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SOURCE_LIST")
        rows.extend(result.get("files",[]))
        if len(rows)>15000:raise RuntimeError("DRIVE_SOURCE_LIST_TOO_LARGE_FOR_BOUNDED_BATCH")
        token=result.get("nextPageToken")
        if not token:return rows
OUT=pathlib.Path("v095_2026_source_archives")
def digest(b):return hashlib.sha256(b).hexdigest()
def taifex_spread_order_evidence(raw,month):
    """Official TAIFEX daily aggregate spread order report: title row + header.

    CSV title is NOT its header. This is daily summary, not minute/tick data.
    Infer no publication timestamp and do not certify downstream metrics.
    """
    from scripts.v093_taifex_independent import native_text
    rows=csv.reader(io.StringIO(native_text(raw).rstrip(chr(26)+" \\t\\r\\n")))
    title=next(rows,[])
    header=[x.strip() for x in next(rows,[])]
    expected=["交易日期","商品代號","價差委託成交量(B+S)","市場總成交量(B+S)","價差委託成交比率(%)"]
    if not title or title[0].strip()!="期貨價差委託成交概況表" or header!=expected:
        raise ValueError("TAIFEX_SPREAD_NATIVE_TITLE_HEADER_MISMATCH")
    dates=set();n=0
    for row in rows:
        if not any(x.strip() for x in row):continue
        row=[x.strip() for x in row]
        if len(row)!=5:raise ValueError("TAIFEX_SPREAD_ROW_WIDTH")
        stamp,symbol,spread,total,percentage=row
        if not re.fullmatch(r"20\\d{6}",stamp) or stamp[:6]!=month.replace("-",""):
            raise ValueError("TAIFEX_SPREAD_DATE_OUTSIDE_REQUEST_MONTH")
        try:date=dt.datetime.strptime(stamp,"%Y%m%d").date()
        except ValueError:raise ValueError("TAIFEX_SPREAD_INVALID_DATE")
        if not symbol or not re.fullmatch(r"[A-Z0-9]{2,12}",symbol):
            raise ValueError("TAIFEX_SPREAD_INVALID_CONTRACT")
        if not re.fullmatch(r"\\d+",spread) or not re.fullmatch(r"\\d+",total):
            raise ValueError("TAIFEX_SPREAD_VOLUME_NOT_INT")
        if int(spread)>int(total):raise ValueError("TAIFEX_SPREAD_VOLUME_EXCEEDS_TOTAL")
        try:ratio=decimal.Decimal(percentage)
        except decimal.InvalidOperation:raise ValueError("TAIFEX_SPREAD_RATIO_FORMAT")
        if not decimal.Decimal(0)<=ratio<=decimal.Decimal(100):
            raise ValueError("TAIFEX_SPREAD_RATIO_RANGE")
        if int(total)==0 and int(spread)>0:raise ValueError("TAIFEX_SPREAD_DIVISION_BY_ZERO")
        if int(total)>0 and abs(ratio-(decimal.Decimal(100)*int(spread)/int(total)))>decimal.Decimal("1"):
            raise ValueError("TAIFEX_SPREAD_RATIO_INCONSISTENT")
        dates.add(date.isoformat());n+=1
    if not n or len(dates)!=1:raise ValueError("TAIFEX_SPREAD_EMPTY_OR_MULTI_DATE")
    return {"rows":n,"dates":sorted(dates),"source_native_type":"TAIFEX_DAILY_SPREAD_ORDER_SUMMARY",
            "release_timestamp_verified":False,"PIT":False}

def validate_zip(b,source,month):
    """Accept only two documented manifest layouts, never unlabeled ZIPs.

    V093_UNIT_MANIFEST: source/month/units[file,sha256]
    TDCC_NATIVE_ORIGINALS: source/period/immutable_originals[archive_path,sha256]
    Both must be SHA-verifiable at member level; no legacy bare-archive promote.
    """
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        infos=z.infolist()
        if not infos or len(infos)>200 or sum(x.file_size for x in infos)>150_000_000:
            raise ValueError("ZIP_EXPANSION_LIMIT")
        if any(x.flag_bits & 1 or x.file_size>MAX_BYTES or x.filename.startswith("/")
               or ".." in pathlib.PurePosixPath(x.filename).parts for x in infos):
            raise ValueError("UNSAFE_ARCHIVE")
        if z.testzip():raise ValueError("ZIP_CRC")
        manifests=[x.filename for x in infos if pathlib.PurePosixPath(x.filename).name
                   in ("manifest.json","complement_manifest_R1.json")]
        if len(manifests)==0 and source=="TAIFEX":
            csvfiles=[x for x in infos if not x.is_dir() and x.filename.lower().endswith(".csv")]
            if len(infos)!=1 or len(csvfiles)!=1:raise ValueError("TAIFEX_NATIVE_ZIP_NOT_SINGLE_CSV")
            from scripts.v093_taifex_independent import csv_evidence,native_text
            year,mm=map(int,month.split("-"))
            start=dt.date(year,mm,1);end=dt.date(year,mm,calendar.monthrange(year,mm)[1])
            native=z.read(csvfiles[0])
            if native_text(native).lstrip().startswith("期貨價差委託成交概況表"):
                evidence=taifex_spread_order_evidence(native,month)
                return 1
            evidence=csv_evidence(native,start,end)
            if evidence.get("rows",0)<1:raise ValueError("TAIFEX_NATIVE_CSV_NO_ROWS")
            lo=evidence.get("content_period",{}).get("min")
            hi=evidence.get("content_period",{}).get("max")
            if not lo or not hi or lo[:7]!=month or hi[:7]!=month:
                raise ValueError("TAIFEX_NATIVE_CSV_MONTH_INCONSISTENT")
            return 1
        if len(manifests)!=1:raise ValueError("MISSING_OR_DUPLICATE_MANIFEST")
        m=json.loads(z.read(manifests[0]))
        manifest_period=m.get("month",m.get("period"))
        if m.get("source")!=source or manifest_period!=month:
            raise ValueError("MANIFEST_SOURCE_MONTH_MISMATCH")
        if isinstance(m.get("units"),list) and m["units"]:
            entries=m["units"];key="file";fmt="V093_UNIT_MANIFEST"
        elif isinstance(m.get("immutable_originals"),list) and m["immutable_originals"]:
            entries=m["immutable_originals"];key="archive_path";fmt="TDCC_NATIVE_ORIGINALS"
        elif (source=="TDCC"
              and pathlib.PurePosixPath(manifests[0]).name=="complement_manifest_R1.json"
              and isinstance(m.get("files"),list) and m["files"]):
            entries=m["files"];key="file";fmt="TDCC_COMPLEMENT_R1"
        else:raise ValueError("UNSUPPORTED_MANIFEST_VERSION")
        archive_names={i.filename for i in infos}
        declared=set()
        for x in entries:
            if not isinstance(x,dict):raise ValueError("MANIFEST_MEMBER_TYPE")
            path=x.get(key)
            if not isinstance(path,str) or not path:
                raise ValueError("MANIFEST_MEMBER_MISSING_OR_AMBIGUOUS")
            if path not in archive_names:
                matches=[n for n in archive_names
                    if pathlib.PurePosixPath(n).name==pathlib.PurePosixPath(path).name]
                if len(matches)!=1:
                    raise ValueError("MANIFEST_MEMBER_MISSING_OR_AMBIGUOUS")
                path=matches[0]
            if path==manifests[0]:raise ValueError("MANIFEST_MEMBER_POINTS_TO_MANIFEST")
            if path in declared:raise ValueError("MANIFEST_DUPLICATE_MEMBER")
            declared.add(path)
            member_sha=x.get("sha256")
            if not isinstance(member_sha,str) or len(member_sha)!=64 or any(c not in "0123456789abcdef" for c in member_sha):
                raise ValueError("MANIFEST_MEMBER_SHA_REQUIRED")
            if digest(z.read(path))!=member_sha:raise ValueError("MANIFEST_MEMBER_SHA_MISMATCH")
        if set(archive_names)-{manifests[0]}!=declared:
            raise ValueError("UNDECLARED_OR_MISSING_ARCHIVE_MEMBER")
        return len(entries)

def main():
    if SOURCE not in ("MOPS","TDCC","TAIFEX","NDC"):raise ValueError("INVALID_SOURCE")
    OUT.mkdir(exist_ok=True)
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    months=[f"2026-{n:02d}" for n in range(1,today.month+1)]
    d=service()
    old=[x for x in ls(d,YEAR_PARENT) if x["name"]==SOURCE and x["mimeType"]==FOLDER]
    if len(old)!=1:raise RuntimeError("UNIQUE_LEGACY_SOURCE_DIRECTORY_MISSING")
    new=BRONZE_ROOTS[SOURCE]
    completed=[];blocked=[];scanned=0;reused=0
    for month in months:
        src=[x for x in ls(d,old[0]["id"]) if x["name"]==month and x["mimeType"]==FOLDER]
        if len(src)!=1:
            blocked.append({"month":month,"state":"V093_MONTH_FOLDER_NOT_UNIQUE_OR_MISSING"})
            continue
        items=ls(d,src[0]["id"])
        dest=folder(d,new,month+"_V093_REUSE_CANDIDATE")
        stored={x.get("md5Checksum") for x in ls(d,dest) if x.get("md5Checksum")}
        for item in sorted(items,key=lambda x:x["name"]):
            if not item["name"].lower().endswith(".zip"):continue
            if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
            if item.get("md5Checksum") and item["md5Checksum"] in stored:
                reused+=1
                continue
            scanned+=1
            try:
                if int(item.get("size",0))>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                b=d.files().get_media(fileId=item["id"]).execute()
                if len(b)>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                members=validate_zip(b,SOURCE,month)
                with zipfile.ZipFile(io.BytesIO(b)) as zz:
                    had_native_manifest=any(pathlib.PurePosixPath(x.filename).name in ("manifest.json","complement_manifest_R1.json")
                                            for x in zz.infolist())
                name="V095_V093_"+SOURCE+"_"+month+"_"+digest(b)[:24]+".zip"
                fid,action=save(d,dest,name,b)
                completed.append({"month":month,"source":SOURCE,"member_count":members,
                                  "sha256":digest(b),"file_id":fid,"action":action,
                                  "state":("STORAGE_SHA_CRC_MANIFEST_PASS_NATIVE_SCHEMA_PENDING" if had_native_manifest
                                   else "TAIFEX_SINGLE_CSV_NATIVE_SCHEMA_DATE_PASS_PIT_PENDING")})
            except Exception as e:
                blocked.append({"month":month,"name_digest":digest(item["name"].encode())[:12],
                                "reason":type(e).__name__+":"+str(e)[:110]})
        if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
    import collections
    blocked_reasons=dict(collections.Counter(
        str(x.get("reason",x.get("state",""))).split(":",1)[-1].split(":",1)[0]
        for x in blocked))
    out={"source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),"completed_archives":completed,
         "blocked":blocked[:50],"blocked_reason_counts":blocked_reasons,"scanned":scanned,"previously_reused_archive_skips":reused,
         "new_bronze_candidate_archives":sum(x["action"]=="CREATED" for x in completed),
         "native_dataset_schema_verified":False,"silver_conversion":"BLOCKED_PENDING_APPROVED_ADAPTER",
         "gold_conversion":"BLOCKED_PENDING_SILVER_AND_PIT",
         "historical_pit_verified":False,"year_complete":False}
    (OUT/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":SOURCE,"new_archives":out["new_bronze_candidate_archives"],
                      "scanned":scanned,"blocked":len(blocked),"blocked_reasons":blocked_reasons,"unchanged_archive_skipped":reused,
                      "silver":out["silver_conversion"],"gold":out["gold_conversion"]},ensure_ascii=False))
if __name__=="__main__":main()
