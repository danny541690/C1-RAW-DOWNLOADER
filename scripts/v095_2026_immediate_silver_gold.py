#!/usr/bin/env python3
"""Immediately turn verified 2026 source Bronze candidates into isolated Silver and
available descriptive Gold. No full-period gate; source ZIP is SHA-verified and
never overwritten. Unsupported dataset families are explicitly deferred.

Supported:
 MOPS official monthly revenue HTML (11 column CP950) -> numeric Silver; YoY/MoM Gold.
 TDCC weekly distribution native JSONL -> typed Silver; tier/week changes Gold.
 TAIFEX native daily spread-order 5-column CSV -> typed Silver; spread share Gold.
 NDC official historical ZIP/XLSX -> original cell-preserving Silver, Gold held
   until series semantics & original publication timestamps are established.
All Gold is descriptive AS-RETRIEVED, not historical PIT or 400+ production.
"""
import collections,csv,datetime as dt,decimal,hashlib,html,io,json,os,pathlib,re,zipfile
import pyarrow as pa,pyarrow.parquet as pq
from openpyxl import load_workbook
from scripts.v095_2026_annual_consolidated import service,BRONZE_ROOTS,FOLDER
from scripts.v095_2026_four_source_archive_intake import ls,validate_zip,taifex_spread_order_evidence
from scripts.v095_ultimate_r1_november_official import folder,save
from scripts.v095_market_release_taifex_history_merge import load as load_sha_archived
from scripts.v095_market_release_calendar_drive_archive import archive as publish_audit
YEAR=int(os.environ.get("V095_DATA_YEAR","2026"))
if YEAR not in (2025,2026):raise ValueError("ONLY_2025_2026")
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
SILVER={"MOPS":"1ick4kRSlmz1ukibDq3TOD7QQxiBHtzWb",
"TDCC":"1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U",
"TAIFEX":"1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8",
"NDC":"1_KDD5xM9IeyBLSfDRppnrjAYQTEnGPRz"}
GOLD="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
OUT=pathlib.Path("v095_2026_immediate_downstream" if YEAR==2026 else "v095_2025_immediate_downstream")
MAX_PER_RUN=max(1,min(6,int(os.getenv("V095_DOWNSTREAM_BATCH","3"))))
D=decimal.Decimal
def sha(x):return hashlib.sha256(x).hexdigest()
def numeric(x):
    if x is None:return None
    x=str(x).strip().replace(",","").replace("−","-")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",x):return None
    return D(x)
def clean(s):return html.unescape(re.sub(r"<[^>]*>","",s)).strip()
def parse_mops(z,manifest,month,bronze_id,archive_sha):
    raw=[];seen=set();bad=0
    for unit in manifest.get("units",[]):
        if not isinstance(unit,dict) or not str(unit.get("name","")).startswith(("revenue_sii_","revenue_otc_")):continue
        name=unit["file"]
        member=[x for x in z.namelist() if x==name or pathlib.PurePosixPath(x).name==pathlib.PurePosixPath(name).name]
        if len(member)!=1:raise ValueError("MOPS_REVENUE_MEMBER_NOT_UNIQUE")
        b=z.read(member[0])
        if sha(b)!=unit.get("sha256"):raise ValueError("MOPS_MEMBER_SHA")
        text=b.decode("cp950")
        roc=int(month[:4])-1911;m=int(month[-2:])
        if f"{roc}年{m}月份" not in text and f"{roc}年{m:02d}月份" not in text:
            raise ValueError("MOPS_REVENUE_HTML_PERIOD_NOT_PROVEN")
        market="TSE" if "revenue_sii_" in unit["name"] else "OTC"
        for tr in re.findall(r"<tr\b[^>]*\balign\s*=\s*['\"]?right['\"]?[^>]*>(.*?)</tr>",text,flags=re.I|re.S):
            cells=[clean(y) for y in re.findall(r"<td\b[^>]*>(.*?)</td>",tr,flags=re.I|re.S)]
            if len(cells)!=11 or not re.fullmatch(r"\d{4}",cells[0]):continue
            key=(market,cells[0])
            if key in seen:raise ValueError("MOPS_DUPLICATE_REVENUE_STOCK")
            seen.add(key)
            vals=[numeric(x) for x in cells[2:10]]
            if vals[0] is None:bad+=1
            raw.append(dict(source="MOPS",market=market,stock_id=cells[0],report_month=month,
              name=cells[1],native_revenue_thousand_ntd=vals[0],
              revenue_億元=vals[0]/D("100000") if vals[0] is not None else None,
              prior_month_億元=vals[1]/D("100000") if vals[1] is not None else None,
              yoy_pct_reported=vals[4],
              mom_pct_reported=vals[3],
              raw_note=cells[10],source_bronze_id=bronze_id,source_zip_sha256=archive_sha,
              source_member=member[0],source_member_sha256=sha(b),
              published_at=None,pit_verified=False))
    if not raw:raise ValueError("NO_TYPED_MOPS_REVENUE_MEMBER")
    if bad:raise ValueError("MOPS_REVENUE_NUMERIC_ROWS_UNVERIFIED")
    gold=[{"source":"MOPS","report_month":r["report_month"],"market":r["market"],
       "stock_id":r["stock_id"],"revenue_億元":r["revenue_億元"],
       "mom_pct_reported":r["mom_pct_reported"],"yoy_pct_reported":r["yoy_pct_reported"],
       "source_zip_sha256":archive_sha,"historical_pit_verified":False,
       "usage":"DESCRIPTIVE_ONLY_NO_LOOKAHEAD_BACKTEST"} for r in raw]
    return raw,gold,"MONTHLY_REVENUE_ONLY"
def parse_tdcc(z,manifest,month,bronze_id,archive_sha):
    units=manifest.get("immutable_originals") or manifest.get("files") or manifest.get("units") or []
    rows=[];seen=set();bad=0
    for unit in units:
        path=unit.get("archive_path") or unit.get("file")
        matches=[x for x in z.namelist() if x==path or pathlib.PurePosixPath(x).name==pathlib.PurePosixPath(path).name]
        if len(matches)!=1:raise ValueError("TDCC_MEMBER_NOT_UNIQUE")
        member=matches[0]
        if not member.lower().endswith(".jsonl"):continue
        b=z.read(member)
        if sha(b)!=unit.get("sha256"):raise ValueError("TDCC_MEMBER_SHA")
        for idx,line in enumerate(b.splitlines()):
            if not line.strip():continue
            obj=json.loads(line);record=obj.get("source_record") if isinstance(obj,dict) else None
            if not isinstance(record,dict):raise ValueError("TDCC_SOURCE_RECORD_MISSING")
            stamp=str(record.get("資料日期",""))
            if not re.fullmatch(r"20\d{6}",stamp) or stamp[:6]!=month.replace("-",""):
                raise ValueError("TDCC_SNAPSHOT_DATE_MISMATCH")
            code=str(record.get("證券代號","")).strip()
            tier=str(record.get("持股分級","")).strip()
            if not code or not tier:raise ValueError("TDCC_CODE_OR_TIER_MISSING")
            key=(stamp,code,tier)
            if key in seen:raise ValueError("TDCC_DUPLICATE_SNAPSHOT_STOCK_TIER")
            seen.add(key)
            people=numeric(record.get("人數"));shares=numeric(record.get("股數"))
            ratio=numeric(record.get("占集保庫存數比例%"))
            if people is None or shares is None or ratio is None or min(people,shares,ratio)<0:
                bad+=1;continue
            if people!=people.to_integral_value() or shares!=shares.to_integral_value() or ratio>100:
                bad+=1;continue
            rows.append(dict(source="TDCC",snapshot_date=f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}",
             stock_id=code,holding_tier=tier,people_count=int(people),shares=int(shares),
             share_percent=ratio,native_record_json=json.dumps(record,ensure_ascii=False),
             source_bronze_id=bronze_id,source_zip_sha256=archive_sha,source_member=member,
             source_member_sha256=sha(b),native_row_index=idx,published_at=None,pit_verified=False))
    if bad:raise ValueError("TDCC_INVALID_NATIVE_NUMERIC_ROWS")
    if not rows:raise ValueError("NO_TYPED_TDCC_NATIVE_JSONL")
    previous={};gold=[]
    for row in sorted(rows,key=lambda r:(r["stock_id"],r["holding_tier"],r["snapshot_date"])):
        key=(row["stock_id"],row["holding_tier"])
        prev=previous.get(key)
        gold.append(dict(source="TDCC",snapshot_date=row["snapshot_date"],
          stock_id=row["stock_id"],holding_tier=row["holding_tier"],
          shares=row["shares"],people_count=row["people_count"],
          wow_shares=None if prev is None else row["shares"]-prev["shares"],
          wow_people=None if prev is None else row["people_count"]-prev["people_count"],
          source_zip_sha256=archive_sha,historical_pit_verified=False,
          usage="DESCRIPTIVE_ONLY_NO_LOOKAHEAD_BACKTEST"))
        previous[key]=row
    return rows,gold,"WEEKLY_OWNERSHIP_PARTITION"
def parse_taifex(z,month,bronze_id,archive_sha,manifest=None):
    # Two distinct native TAIFEX formats: daily spread summary and monthly
    # historical original CSV in hash-verified manifest wrapper.
    units=(manifest or {}).get("units") or []
    dataset=units[0].get("dataset") if len(units)==1 and isinstance(units[0],dict) else None
    if dataset in ("futDataDown","largeTraderFutDown","dlLargeTraderOptDown"):
        from scripts.v093_taifex_monthly_content import inspect_month_csv,SCHEMAS
        from scripts.v093_taifex_independent import native_text,parse_date
        members=[x for x in z.namelist() if x.lower().endswith(".csv")]
        if len(members)!=1:raise ValueError("TAIFEX_HISTORY_CSV_MEMBER_NOT_UNIQUE")
        filename=members[0];raw=z.read(filename)
        if sha(raw)!=units[0].get("sha256"):raise ValueError("TAIFEX_HISTORY_MEMBER_SHA")
        evidence=inspect_month_csv(raw,{"資料集":dataset,"期間":month})
        reader=csv.reader(io.StringIO(native_text(raw).rstrip(chr(26)+chr(32)+chr(9)+chr(13)+chr(10))))
        header=next(reader,[])
        if header!=SCHEMAS[dataset]:raise ValueError("TAIFEX_HISTORY_HEADER_CONTRACT_MISMATCH")
        rows=[]
        for n,values in enumerate(reader,1):
            if not any(x.strip() for x in values):continue
            if len(values)==1 and values[0].startswith(("備註","月份類別格式","交易人類別格式","-表")):continue
            if len(values)!=len(header):raise ValueError("TAIFEX_HISTORY_ROW_WIDTH_UNVERIFIED")
            when=parse_date(values[0])
            if not when or when.isoformat()[:7]!=month:
                raise ValueError("TAIFEX_HISTORY_TRADE_DATE_MISMATCH")
            rows.append(dict(source="TAIFEX",trade_date=when.isoformat(),dataset=dataset,
                raw_record_json=json.dumps(dict(zip(header,values)),ensure_ascii=False),
                source_member=filename,source_member_sha256=sha(raw),
                source_bronze_id=bronze_id,source_zip_sha256=archive_sha,
                origin_legacy_file_id=units[0].get("origin_legacy_file_id"),
                native_numeric_pit_verified=False,published_at=None,pit_verified=False))
        if not rows or len(rows)!=evidence["rows"]:raise ValueError("TAIFEX_HISTORY_ROW_COUNT_DISAGREES_WITH_SOURCE_VALIDATOR")
        return rows,[],"DAILY_HISTORY_"+dataset+"_NATIVE_VALUES"
    members=[x for x in z.namelist() if x.lower().endswith(".csv")]
    if len(members)!=1:raise ValueError("TAIFEX_TYPED_SPREAD_REQUIRES_SINGLE_CSV")
    from scripts.v093_taifex_independent import native_text
    data=z.read(members[0])
    taifex_spread_order_evidence(data,month)
    reader=csv.reader(io.StringIO(native_text(data)))
    next(reader);next(reader)
    rows=[];gold=[]
    for r in reader:
        if not any(x.strip() for x in r):continue
        date,symbol,spread,total,ratio=[x.strip() for x in r]
        day=f"{date[:4]}-{date[4:6]}-{date[6:]}"
        rows.append(dict(source="TAIFEX",trade_date=day,contract_code=symbol,
           spread_volume=int(spread),total_market_volume=int(total),
           reported_spread_pct=D(ratio),source_member=members[0],source_bronze_id=bronze_id,
           source_zip_sha256=archive_sha,published_at=None,pit_verified=False))
        gold.append(dict(source="TAIFEX",trade_date=day,contract_code=symbol,
           spread_volume=int(spread),reported_spread_pct=D(ratio),
           source_zip_sha256=archive_sha,historical_pit_verified=False,
           usage="DESCRIPTIVE_ONLY_NO_LOOKAHEAD_BACKTEST"))
    return rows,gold,"DAILY_SPREAD_ORDER_SUMMARY"
def parquet(rows):
    if not rows:raise ValueError("PARQUET_EMPTY_ROWS")
    buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows),buf,compression="zstd")
    blob=buf.getvalue()
    if pq.read_metadata(io.BytesIO(blob)).num_rows!=len(rows):raise ValueError("PARQUET_ROW_READBACK")
    return blob
def confirm_lineage(d,source,bronze_id,bronze_hash,silver_id,silver_hash,
                    silver_rows,gold_id=None,gold_hash=None,gold_rows=None):
    """Bidirectional Bronze→Silver→Gold and Gold→Silver→Bronze receipt.
    File IDs and content hashes are read back, never inferred from file names.
    """
    if bronze_id!="OFFICIAL_G0_SHA_ARCHIVE":
        raw=d.files().get_media(fileId=bronze_id).execute()
        if sha(raw)!=bronze_hash:raise ValueError("LINEAGE_BRONZE_HASH_READBACK_MISMATCH")
    silver_bytes=d.files().get_media(fileId=silver_id).execute()
    if sha(silver_bytes)!=silver_hash:raise ValueError("LINEAGE_SILVER_HASH_READBACK_MISMATCH")
    sv=pq.read_table(io.BytesIO(silver_bytes))
    if sv.num_rows!=silver_rows:raise ValueError("LINEAGE_SILVER_ROW_COUNT")
    for field,value in (("source_zip_sha256",bronze_hash),):
        if field not in sv.column_names:raise ValueError("LINEAGE_SILVER_MISSING_PARENT_FIELD")
        if any(x!=value for x in sv.column(field).to_pylist()):
            raise ValueError("LINEAGE_SILVER_TO_BRONZE_REVERSE_MISMATCH")
    trace={"bronze":{"id":bronze_id,"sha256":bronze_hash},
       "silver":{"id":silver_id,"sha256":silver_hash,"row_count":silver_rows},
       "gold":None,"forward_verified":True,"reverse_verified":True,
       "historical_pit_certified":False}
    if gold_id:
        raw=d.files().get_media(fileId=gold_id).execute()
        if sha(raw)!=gold_hash:raise ValueError("LINEAGE_GOLD_HASH_READBACK_MISMATCH")
        gt=pq.read_table(io.BytesIO(raw))
        if gt.num_rows!=gold_rows:raise ValueError("LINEAGE_GOLD_ROW_COUNT")
        for field,expect in (("source_zip_sha256",bronze_hash),("parent_silver_sha256",silver_hash)):
            if field not in gt.column_names:raise ValueError("LINEAGE_GOLD_MISSING_PARENT_FIELD")
            if any(x!=expect for x in gt.column(field).to_pylist()):
                raise ValueError("LINEAGE_GOLD_TO_SILVER_TO_BRONZE_REVERSE_MISMATCH")
        trace["gold"]={"id":gold_id,"sha256":gold_hash,"row_count":gold_rows}
    return trace
def write_pair(d,source,month,bronze_id,bronze_sha,silver,gold,dataset):
    sf=folder(d,SILVER[source],month+"_INCREMENTAL_CANDIDATE")
    silver_blob=parquet(silver)
    silver_name=f"V095_{source}_{month.replace('-','')}_{bronze_sha[:20]}_SILVER_{dataset}.parquet"
    silver_id,_=save(d,sf,silver_name,silver_blob)
    silver_hash=sha(silver_blob)
    report={"source":source,"month":month,"dataset":dataset,
      "bronze_id":bronze_id,"bronze_sha256":bronze_sha,
      "silver_id":silver_id,"silver_sha256":silver_hash,
      "silver_rows":len(silver),"silver":"CANDIDATE","PIT":False,
      "all_400plus_factors_complete":False,"full_period":False}
    gold_id=None;gold_hash=None
    if gold:
        try:
            for item in gold:
                item["parent_silver_sha256"]=silver_hash
                item["parent_silver_id"]=silver_id
            gf=folder(d,GOLD,month+"_INCREMENTAL_DESCRIPTIVE_"+source)
            gold_blob=parquet(gold)
            gold_name=f"V095_{source}_{month.replace('-','')}_{bronze_sha[:20]}_GOLD_DESCRIPTIVE_{dataset}.parquet"
            gold_id,_=save(d,gf,gold_name,gold_blob)
            gold_hash=sha(gold_blob)
            report.update(gold_id=gold_id,gold_sha256=gold_hash,gold_rows=len(gold),
             gold="DESCRIPTIVE_CANDIDATE_NOT_PIT")
        except Exception as ex:
            report.update(gold="DEFERRED_GOLD_CONVERSION_FAILED",
                gold_error=type(ex).__name__+":"+str(ex)[:130])
            gold_id=None;gold_hash=None
    else:report["gold"]="DISABLED_MISSING_VERIFIED_FACTOR_INPUT"
    audit=confirm_lineage(d,source,bronze_id,bronze_sha,silver_id,silver_hash,
        len(silver),gold_id,gold_hash,len(gold) if gold_id else None)
    report["bidirectional_lineage"]=audit
    report["stage_lineage_status"]="PASS" if gold_id else "SILVER_PASS_GOLD_PENDING"
    return report
def candidate_files(d):
    root=BRONZE_ROOTS[SOURCE]
    months=[x for x in ls(d,root) if x["mimeType"]==FOLDER
        and re.fullmatch(fr"{YEAR}-\d{{2}}_V093_REUSE_CANDIDATE",x["name"])]
    output=[]
    for m in sorted(months,key=lambda x:x["name"]):
        for f in ls(d,m["id"]):
            match=re.fullmatch(r"V095_V093_"+SOURCE+fr"_({YEAR}-\d{{2}})_([a-f0-9]{{24}})\.zip",f["name"])
            if match and match[1]==m["name"][:7]:output.append((match[1],f,match[2]))
    return output
def parse_ndc(d):
    from scripts.v093_ndc_independent import parse_bundle
    original,h=load_sha_archived(d,"ndc_current_revised_source","zip")
    receipt_raw,_=load_sha_archived(d,"ndc_monthly_manifest","json")
    meta=json.loads(receipt_raw)
    if meta.get("native_zip_sha256")!=h:raise ValueError("NDC_NATIVE_ZIP_SHA")
    tables=parse_bundle(original)
    rows=[]
    for table in tables:
        for month,values in sorted(table["rows"].items()):
            if month<"2000-01" or month>"2026-11":continue
            rows.append(dict(source="NDC",observation_month=month,
              original_table=table["name"],source_row_index=table["row_numbers"][month],
              native_header_json=json.dumps(table["header"],ensure_ascii=False),
              native_values_json=json.dumps(values,ensure_ascii=False),
              source_zip_sha256=h,observation_month_certified=True,
              historical_vintage_certified=False,published_at=None,pit_verified=False))
    if not rows:raise ValueError("NDC_NO_OFFICIAL_OBSERVATION_ROWS")
    months={r["observation_month"] for r in rows}
    if len(months)!=meta.get("month_rows"):
        raise ValueError("NDC_OFFICIAL_MANIFEST_MONTH_COUNT_DIFFERENCE")
    return rows,h
def missing_factor_register(source,done,blocked):
    import csv as _csv
    contract_path=pathlib.Path("governance/v095/DATASET_CONTRACTS.csv")
    with contract_path.open(encoding="utf-8-sig",newline="") as f:
        entries=[x for x in _csv.DictReader(f) if x["source_class_id"]==source]
    supported=set(x["dataset"] for x in done)
    list_rows=[]
    for x in entries:
        list_rows.append({"dataset_id":x["dataset_id"],"source":source,
          "status":"DISABLED_PENDING_VERIFIED_INPUT_AND_PIT",
          "no_zero_imputation":True,"silver_typed_supported_in_this_batch":
             bool(supported),
          "reason":"contract family coverage/PIT not certified, candidate data does not imply official historical release"})
    derived={
     "MOPS":["24_MONTH_REVENUE_HIGH","REVENUE_ACCELERATION","TTM_EPS"],
     "TDCC":["CROSS_WEEK_CONCENTRATION","LARGE_HOLDER_TIER_DELTA","STOCK_LEVEL_OWNERSHIP_PIT"],
     "TAIFEX":["OI_CHANGE","INSTITUTIONAL_FUTURES_POSITION","PUT_CALL_RATIO"],
     "NDC":["PIT_BUSINESS_CYCLE_SCORE","ASOF_MACRO_SIGNALS","HISTORICAL_VINTAGE_FEATURES"]
    }
    for factor in derived[source]:
        list_rows.append({"source":source,"factor":factor,
           "status":"DISABLED_PENDING_HISTORY_OR_PIT","no_zero_imputation":True,
           "reason":"unverified source time/vintage, insufficient typed lookback or absent data"})
    for error in blocked:
        list_rows.append({"source":source,"source_archive_id":error.get("source_archive_id"),
           "month":error.get("month"),"factor":"SOURCE_DEPENDENT_METRICS",
           "status":"NULL_AFTER_THREE_ATTEMPTS",
           "no_zero_imputation":True,"reason":error.get("reason")})
    return list_rows

def convert_with_three_attempts(do,source,month,identifier):
    errors=[]
    for attempt in (1,2,3):
        try:return do(),[]
        except Exception as ex:
            error={"source":source,"month":month,"input":identifier,"attempt":attempt,
              "type":type(ex).__name__,"error":str(ex)[:200]}
            errors.append(error)
            # Repeat only the bounded candidate, not the whole run.
    return None,errors

def main():
    if SOURCE not in SILVER:raise ValueError("IMMEDIATE_DOWNSTREAM_SOURCE_UNKNOWN")
    OUT.mkdir(exist_ok=True);d=service()
    done=[];reused=0;blocked=[];considered=0
    if SOURCE=="NDC" and YEAR==2025:
        blocked.append({"month":"2025","source_archive_id":None,"state":"BLOCKED_NDC_2025_HISTORICAL_VINTAGE_ADAPTER_NOT_CERTIFIED","reason":"Requires dedicated historical vintage and observation period validation"})
    elif SOURCE=="NDC":
        def execute_ndc():
            rows,h=parse_ndc(d)
            return write_pair(d,SOURCE,"2026-09","OFFICIAL_G0_SHA_ARCHIVE",h,rows,[],
                "NDC_REVISED_NATIVE_CELLS")
        result,errors=convert_with_three_attempts(execute_ndc,SOURCE,"2026-09","OFFICIAL_G0_SHA_ARCHIVE")
        if result:done.append(result)
        else:blocked.append({"month":"2026-09","source_archive_id":"OFFICIAL_G0_SHA_ARCHIVE",
           "attempts":3,"reason":errors[-1]["error"],"state":"NULL_AFTER_THREE_ATTEMPTS"})
    else:
        for month,f,prefix in candidate_files(d):
            if len(done)>=MAX_PER_RUN or considered>=MAX_PER_RUN*12:break
            considered+=1
            sf=folder(d,SILVER[SOURCE],month+"_INCREMENTAL_CANDIDATE")
            recorded=ls(d,sf)
            silver_prefix=f"V095_{SOURCE}_{month.replace('-','')}_{prefix[:20]}_SILVER_"
            if any(x["name"].startswith(silver_prefix) and x["name"].endswith(".parquet")
                   for x in recorded):
                reused+=1;continue
            quarantine_name=f"V095_{SOURCE}_{month.replace('-','')}_{prefix[:20]}_DOWNSTREAM_NULL_3X.json"
            if any(x["name"]==quarantine_name for x in recorded):
                reused+=1;continue
            def convert():
                blob=d.files().get_media(fileId=f["id"]).execute()
                h=sha(blob)
                if h[:24]!=prefix:raise ValueError("BRONZE_ARCHIVE_SHA_FILENAME")
                validate_zip(blob,SOURCE,month)
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    manifests=[x for x in z.namelist() if pathlib.PurePosixPath(x).name
                        in ("manifest.json","complement_manifest_R1.json")]
                    manifest=json.loads(z.read(manifests[0])) if manifests else {}
                    if SOURCE=="MOPS":sil,go,dataset=parse_mops(z,manifest,month,f["id"],h)
                    elif SOURCE=="TDCC":sil,go,dataset=parse_tdcc(z,manifest,month,f["id"],h)
                    else:sil,go,dataset=parse_taifex(z,month,f["id"],h,manifest)
                return write_pair(d,SOURCE,month,f["id"],h,sil,go,dataset)
            success,errors=convert_with_three_attempts(convert,SOURCE,month,f["id"])
            if success:
                done.append(success)
            else:
                failure={"month":month,"source_archive_id":f["id"],"sha_prefix":prefix,
                  "attempts":3,"reason":errors[-1]["type"]+":"+errors[-1]["error"],
                  "all_attempts":errors,"state":"NULL_AFTER_THREE_ATTEMPTS"}
                blocked.append(failure)
                # Durable source scoped immutable exception (reused on next run).
                save(d,sf,quarantine_name,json.dumps(failure,ensure_ascii=False,sort_keys=True).encode("utf-8"))
    result={"source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),"candidate_files_examined":considered,
      "converted":done,"silver_converted":len(done),
      "gold_descriptive_created":sum(x.get("gold_id") is not None for x in done),
      "candidate_reused":reused,"blocked":blocked,"blocked_count":len(blocked),
      "run_bronze_incremental_independently":True,"whole_month_complete":False,
      "historical_PIT_certified":False,"Gold_400plus_certified":False,"data_year":YEAR}
    p=OUT/"result.json";p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":SOURCE,"silver_converted":len(done),
      "gold_descriptive_created":result["gold_descriptive_created"],
      "candidate_reused":reused,"blocked":len(blocked),
      "blocked_details":blocked[:4],"PIT":False},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
