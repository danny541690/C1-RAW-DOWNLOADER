#!/usr/bin/env python3
"""Safe four-source 2026 archived Bronze candidate intake.

v0.93 first: copy only original native ZIP archives after SHA/CRC and source/month
manifest verification into isolated v0.95 staging folders. Never promote archive
CRC as verified financial contents or manufacture Silver/Gold/PIT. Missing
eligible files are reported for dedicated official-source backfill adapters.
"""
import datetime as dt
import calendar, csv, re, decimal
import hashlib, io, json, os, pathlib, sys, zipfile, inspect
from scripts.v095_2026_annual_consolidated import service,BRONZE_ROOTS,FOLDER
from scripts.v095_2026_prior_raw_reuse_audit import YEAR_PARENT
from scripts.v095_ultimate_r1_november_official import folder,save
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
YEAR=int(os.environ.get("V095_DATA_YEAR","2026"))
if YEAR not in (2025,2026):raise ValueError("ONLY_2025_2026_ARCHIVES")
LEGACY_YEAR_ROOT=YEAR_PARENT if YEAR==2026 else "1VB9s43UHEQeZbPbLHOCcFAQewUDfjBOm"
# Verified separate historical TDCC native-original complement archive folder (not the
# same as /2026/TDCC); optional and source-specific, never assume its contents valid.
TDCC_ARCHIVE_SOURCE_FOLDER="103Mc52wF1brnIqfB0mL85UaeW-LcnmXo" if YEAR==2026 else None
MAX_SOURCE_FILES=min(int(os.environ.get("V095_ARCHIVE_BATCH","3")),6)
MAX_BYTES=20_000_000
MAX_INSPECT_PER_RUN=300

def ls(d,folder,only_archives=False):
    rows=[];token=None
    while True:
        result=d.files().list(q="'"+folder+"' in parents and trashed=false"+(" and name contains '.zip'" if only_archives else ""),
          fields="nextPageToken,incompleteSearch,files(id,name,size,mimeType,md5Checksum,createdTime)",pageSize=500,pageToken=token).execute()
        if result.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SOURCE_LIST")
        rows.extend(result.get("files",[]))
        if len(rows)>15000:raise RuntimeError("DRIVE_SOURCE_LIST_TOO_LARGE_FOR_BOUNDED_BATCH")
        token=result.get("nextPageToken")
        if not token:return rows
OUT=pathlib.Path("v095_2026_source_archives" if YEAR==2026 else "v095_2025_source_archives")
def digest(b):return hashlib.sha256(b).hexdigest()
def load_quarantine_ledger(raw):
    """Read exact SHA-backed old JSON, allowing only the historic literal backslash-n suffix."""
    if not isinstance(raw,bytes):raise ValueError("QUARANTINE_LEDGER_NOT_BYTES")
    try:content=raw.decode("utf-8")
    except UnicodeError:raise ValueError("QUARANTINE_LEDGER_BAD_ENCODING")
    try:obj,end=json.JSONDecoder().raw_decode(content)
    except json.JSONDecodeError:raise ValueError("QUARANTINE_LEDGER_BAD_JSON")
    tail=content[end:]
    if tail not in ("", "\\n", "\n") and tail.strip():
        raise ValueError("QUARANTINE_LEDGER_TRAILING_CONTENT")
    if not isinstance(obj,dict):raise ValueError("QUARANTINE_LEDGER_NOT_OBJECT")
    return obj

def taifex_spread_order_evidence(raw,month=None):
    """Official TAIFEX daily aggregate spread order report: title row + header.

    CSV title is NOT its header. This is daily summary, not minute/tick data.
    Infer no publication timestamp and do not certify downstream metrics.
    """
    from scripts.v093_taifex_independent import native_text
    rows=csv.reader(io.StringIO(native_text(raw).rstrip(chr(26)+" \t\r\n")))
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
        if not re.fullmatch(r"20\d{6}",stamp) or (month is not None and stamp[:6]!=month.replace("-","")):
            raise ValueError("TAIFEX_SPREAD_DATE_OUTSIDE_REQUEST_MONTH")
        try:date=dt.datetime.strptime(stamp,"%Y%m%d").date()
        except ValueError:raise ValueError("TAIFEX_SPREAD_INVALID_DATE")
        if not symbol or not re.fullmatch(r"[A-Z0-9]{2,12}",symbol):
            raise ValueError("TAIFEX_SPREAD_INVALID_CONTRACT")
        if not re.fullmatch(r"\d+",spread) or not re.fullmatch(r"\d+",total):
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
        # Older v0.93 MOPS financial statement manifests omit top-level
        # source/month but stamp every unit. Accept only if ALL units agree.
        units_m=m.get("units",[])
        complete_unit_provenance=(source=="MOPS" and isinstance(units_m,list) and bool(units_m)
            and all(isinstance(u,dict) and u.get("source")==source and u.get("month")==month
                    for u in units_m))
        # v0.93 TDCC complement manifests carry source=TDCC_ARCHIVE, not TDCC.
        # Only accept that alias with exact complement manifest, matching month and
        # member SHA validation below; retain the alias as an origin label.
        tdcc_complement=(source=="TDCC" and m.get("source")=="TDCC_ARCHIVE"
             and pathlib.PurePosixPath(manifests[0]).name=="complement_manifest_R1.json"
             and manifest_period==month and isinstance(m.get("files"),list))
        root_identity=(m.get("source")==source and manifest_period==month) or tdcc_complement
        old_mops_unit_identity=(m.get("source") is None and manifest_period is None
                               and complete_unit_provenance)
        if not (root_identity or old_mops_unit_identity):
            raise ValueError("MANIFEST_SOURCE_MONTH_MISMATCH")
        if root_identity and source=="MOPS" and isinstance(units_m,list):
            for u in units_m:
                if not isinstance(u,dict) or (
                    u.get("source") is not None and u.get("source")!=source) or (
                    u.get("month") is not None and u.get("month")!=month):
                    raise ValueError("MANIFEST_UNIT_SOURCE_MONTH_INCONSISTENT")
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
    if SOURCE=="NDC" and YEAR==2026:
        # NDC official series is an observation-month XLSX bundle in one ZIP,
        # not a separate 2026-09/10/11 directory for each publication.
        # Reuse G0's verified native ZIP and receipt instead of inventing gaps.
        from scripts.v095_market_release_taifex_history_merge import load as read_archive
        d=service()
        source_bytes,source_sha=read_archive(d,"ndc_current_revised_source","zip")
        receipt_bytes,_=read_archive(d,"ndc_monthly_manifest","json")
        receipt=json.loads(receipt_bytes)
        if (source_sha!=receipt.get("native_zip_sha256")
                or receipt.get("month_rows",0)<200
                or receipt.get("monthly_observation_last","")<"2026-09"):
            raise ValueError("NDC_OFFICIAL_REVISED_SERIES_MISSING_OR_SHA_MISMATCH")
        result={"source":"NDC","run_id":os.getenv("GITHUB_RUN_ID"),
           "completed_archives":[],"blocked":[],"scanned":0,
           "previously_reused_archive_skips":1,
           "new_bronze_candidate_archives":0,
           "source_archive_sha256":source_sha,
           "confirmed_observation_months":receipt["month_rows"],
           "last_official_observation_month":receipt["monthly_observation_last"],
           "state":"REUSED_SHA_VERIFIED_OFFICIAL_REVISED_SERIES",
           "per_month_legacy_folders_required":False,
           "historical_vintage_PIT_verified":False,
           "silver_conversion":"BLOCKED_PENDING_APPROVED_ADAPTER",
           "gold_conversion":"BLOCKED_PENDING_SILVER_AND_PIT",
           "year_complete":False}
        (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"source":"NDC","new_archives":0,"scanned":0,
            "blocked":0,"unchanged_archive_skipped":1,
            "official_observation_months_reused":receipt["month_rows"],
            "silver":result["silver_conversion"],"gold":result["gold_conversion"]},ensure_ascii=False))
        return
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    months=[f"{YEAR}-{n:02d}" for n in range(1,(today.month if YEAR==2026 else 12)+1)]
    d=service()
    old=[x for x in ls(d,LEGACY_YEAR_ROOT) if x["name"]==SOURCE and x["mimeType"]==FOLDER]
    if len(old)!=1:raise RuntimeError("UNIQUE_LEGACY_SOURCE_DIRECTORY_MISSING")
    new=BRONZE_ROOTS[SOURCE]
    # Source ZIPs are immutable. Store a durable per-validator SHA exception
    # ledger in the source Bronze root so unchanged bad ZIPs are not reopened
    # every run. Any code change invalidates the cache automatically.
    validator_fingerprint=(inspect.getsource(validate_zip)
         +inspect.getsource(taifex_spread_order_evidence)
         +str(MAX_BYTES))
    validator_version=digest(validator_fingerprint.encode("utf-8"))[:20]
    ledger_prefix="V095_QUARANTINE_"+str(YEAR)+"_"+SOURCE+"_"+validator_version+"_"
    old_ledgers=[x for x in ls(d,new) if x["name"].startswith(ledger_prefix)
                 and x["name"].endswith(".json")]
    old_ledgers.sort(key=lambda x:x.get("createdTime",""),reverse=True)
    known_failures={}
    if old_ledgers:
        raw=d.files().get_media(fileId=old_ledgers[0]["id"]).execute()
        if not (old_ledgers[0]["name"]==ledger_prefix+digest(raw)[:24]+".json" or old_ledgers[0]["name"].endswith("_"+digest(raw)[:24]+".json")):
            raise ValueError("LEGACY_QUARANTINE_LEDGER_SHA_MISMATCH")
        received=load_quarantine_ledger(raw)
        if received.get("source")!=SOURCE or received.get("validator_version")!=validator_version:
            raise ValueError("LEGACY_QUARANTINE_LEDGER_SOURCE_VERSION_CONFLICT")
        known_failures=received.get("immutable_zip_failures",{})
        if not isinstance(known_failures,dict):raise ValueError("LEGACY_QUARANTINE_LEDGER_BAD_TYPE")
    completed=[];blocked=[];scanned=0;reused=0;cached_quarantine_skips=0
    for month in months:
        # Combine *all verified legacy parent directories* before declaring no ZIP.
        # Avoid a false official gap when TDCC original content is under TDCC_ARCHIVE.
        month_locations=[]
        for origin,source_root in [("TDCC" if SOURCE=="TDCC" else SOURCE,old[0]["id"])]+extra_tdcc_roots:
            src=[x for x in ls(d,source_root) if x["name"]==month and x["mimeType"]==FOLDER]
            if len(src)>1:
                blocked.append({"month":month,"origin":origin,"state":"V093_MONTH_FOLDER_AMBIGUOUS"})
            elif src:
                month_locations.append((origin,src[0]["id"]))
        if not month_locations:
            blocked.append({"month":month,"state":"V093_MONTH_FOLDER_NOT_UNIQUE_OR_MISSING"})
            continue
        items=[]
        for origin,folder_id in month_locations:
            for candidate in ls(d,folder_id,only_archives=True):
                items.append(dict(candidate,_legacy_origin=origin))
        if not items:
            blocked.append({"month":month,"state":"NO_V093_ZIP_IN_ANY_LEGACY_ROOT_NOT_PROVEN_OFFICIAL_MISSING",
                            "searched_origins":[x[0] for x in month_locations]})
            continue
        dest=folder(d,new,month+"_V093_REUSE_CANDIDATE")
        stored={x.get("md5Checksum") for x in ls(d,dest) if x.get("md5Checksum")}
        for item in sorted(items,key=lambda x:x["name"]):
            if not item["name"].lower().endswith(".zip"):continue
            if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
            if item.get("md5Checksum") and item["md5Checksum"] in stored:
                reused+=1
                continue
            candidate_key=item["id"]+"|"+str(item.get("md5Checksum",""))+"|"+str(item.get("size",""))
            if item.get("md5Checksum") and candidate_key in known_failures:
                cached_quarantine_skips+=1
                continue
            scanned+=1
            try:
                if int(item.get("size",0))>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                b=d.files().get_media(fileId=item["id"]).execute()
                if len(b)>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                target_month=month
                try:
                    members=validate_zip(b,SOURCE,month)
                except ValueError as ex:
                    if SOURCE!="TAIFEX" or str(ex)!="TAIFEX_SPREAD_DATE_OUTSIDE_REQUEST_MONTH":
                        raise
                    with zipfile.ZipFile(io.BytesIO(b)) as zz:
                        csv_members=[i for i in zz.infolist() if i.filename.lower().endswith(".csv")]
                        if len(zz.infolist())!=1 or len(csv_members)!=1:
                            raise ValueError("TAIFEX_DATE_REROUTE_INVALID_ZIP")
                        native=taifex_spread_order_evidence(zz.read(csv_members[0]),None)
                    target_month=native["dates"][0][:7]
                    if target_month not in months or dt.date.fromisoformat(native["dates"][0])>today:
                        raise ValueError("TAIFEX_DATE_REROUTE_OUTSIDE_VERIFIED_SCOPE")
                    members=validate_zip(b,SOURCE,target_month)
                with zipfile.ZipFile(io.BytesIO(b)) as zz:
                    had_native_manifest=any(pathlib.PurePosixPath(x.filename).name in ("manifest.json","complement_manifest_R1.json")
                                            for x in zz.infolist())
                name="V095_V093_"+SOURCE+"_"+target_month+"_"+digest(b)[:24]+".zip"
                actual_dest=dest if target_month==month else folder(d,new,target_month+"_V093_REUSE_CANDIDATE")
                fid,action=save(d,actual_dest,name,b)
                completed.append({"month":target_month,"legacy_folder_month":month,
                                  "source_month_reassigned_from_native_date":target_month!=month,
                                  "source":SOURCE,"legacy_source_folder":item.get("_legacy_origin"),"member_count":members,
                                  "sha256":digest(b),"file_id":fid,"action":action,
                                  "state":("STORAGE_SHA_CRC_MANIFEST_PASS_NATIVE_SCHEMA_PENDING" if had_native_manifest
                                   else "TAIFEX_SINGLE_CSV_NATIVE_SCHEMA_DATE_PASS_PIT_PENDING")})
            except Exception as e:
                reason=type(e).__name__+":"+str(e)[:110]
                blocked.append({"month":month,"legacy_source_folder":item.get("_legacy_origin"),
                                "name_digest":digest(item["name"].encode())[:12],
                                "reason":reason})
                # Network and Drive/credential failures must NOT be cached.
                if item.get("md5Checksum") and isinstance(e,ValueError):
                    known_failures[candidate_key]={"month":month,"reason":str(e)[:120]}
        if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
    import collections
    ledger={"source":SOURCE,"year":YEAR,"validator_version":validator_version,
            "immutable_zip_failures":known_failures,
            "policy":"REUSE_ONLY_IF_SAME_DRIVE_ID_MD5_SIZE_AND_VALIDATOR_SHA",
            "PIT_certified":False}
    ledger_bytes=(json.dumps(ledger,ensure_ascii=False,sort_keys=True)+"\n").encode()
    ledger_name=ledger_prefix+str(os.getenv("GITHUB_RUN_ID","LOCAL"))+"_"+digest(ledger_bytes)[:24]+".json"
    ledger_id,ledger_action=save(d,new,ledger_name,ledger_bytes)
    if digest(d.files().get_media(fileId=ledger_id).execute())!=digest(ledger_bytes):
        raise ValueError("LEGACY_QUARANTINE_LEDGER_DRIVE_READBACK_SHA_MISMATCH")
    blocked_reasons=dict(collections.Counter(
        str(x.get("reason",x.get("state",""))).split(":",1)[-1].split(":",1)[0]
        for x in blocked))
    out={"source":SOURCE,"data_year":YEAR,"run_id":os.getenv("GITHUB_RUN_ID"),"completed_archives":completed,
         "blocked":blocked[:50],"blocked_reason_counts":blocked_reasons,"cached_quarantine_skips":cached_quarantine_skips,
         "known_immutable_format_exceptions":len(known_failures),"scanned":scanned,"previously_reused_archive_skips":reused,
         "new_bronze_candidate_archives":sum(x["action"]=="CREATED" for x in completed),
         "native_dataset_schema_verified":False,"silver_conversion":"BLOCKED_PENDING_APPROVED_ADAPTER",
         "gold_conversion":"BLOCKED_PENDING_SILVER_AND_PIT",
         "historical_pit_verified":False,"year_complete":False}
    (OUT/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":SOURCE,"new_archives":out["new_bronze_candidate_archives"],
                      "scanned":scanned,"blocked":len(blocked),"blocked_reasons":blocked_reasons,
                      "cached_quarantine_skips":cached_quarantine_skips,
                      "known_immutable_format_exceptions":len(known_failures),"unchanged_archive_skipped":reused,
                      "silver":out["silver_conversion"],"gold":out["gold_conversion"]},ensure_ascii=False))
if __name__=="__main__":main()
