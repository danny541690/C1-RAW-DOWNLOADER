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
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
SILVER={"MOPS":"1ick4kRSlmz1ukibDq3TOD7QQxiBHtzWb",
"TDCC":"1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U",
"TAIFEX":"1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8",
"NDC":"1_KDD5xM9IeyBLSfDRppnrjAYQTEnGPRz"}
GOLD="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
OUT=pathlib.Path("v095_2026_immediate_downstream")
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
def parse_taifex(z,month,bronze_id,archive_sha):
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
def write_pair(d,source,month,bronze_id,bronze_sha,silver,gold,dataset):
    sf=folder(d,SILVER[source],month+"_INCREMENTAL_CANDIDATE")
    gb=parquet(silver)
    silver_name=f"V095_{source}_{month.replace('-','')}_{bronze_sha[:20]}_SILVER_{dataset}.parquet"
    silver_id,_=save(d,sf,silver_name,gb)
    report={"source":source,"month":month,"dataset":dataset,"bronze_id":bronze_id,
      "bronze_sha256":bronze_sha,"silver_id":silver_id,"silver_sha256":sha(gb),
      "silver_rows":len(silver),"silver":"CANDIDATE","pit_verified":False,"full_period":False}
    if gold:
        gf=folder(d,GOLD,month+"_INCREMENTAL_DESCRIPTIVE_"+source)
        gblob=parquet(gold)
        gold_name=f"V095_{source}_{month.replace('-','')}_{bronze_sha[:20]}_GOLD_DESCRIPTIVE_{dataset}.parquet"
        gold_id,_=save(d,gf,gold_name,gblob)
        report.update(gold_id=gold_id,gold_sha256=sha(gblob),gold_rows=len(gold),
         gold="DESCRIPTIVE_CANDIDATE_NOT_PIT")
    else:report["gold"]="BLOCKED_MISSING_VERIFIED_SERIES_OR_FACTOR_ADAPTER"
    return report
def candidate_files(d):
    root=BRONZE_ROOTS[SOURCE]
    months=[x for x in ls(d,root) if x["mimeType"]==FOLDER
        and re.fullmatch(r"2026-\d{2}_V093_REUSE_CANDIDATE",x["name"])]
    output=[]
    for m in sorted(months,key=lambda x:x["name"]):
        for f in ls(d,m["id"]):
            match=re.fullmatch(r"V095_V093_"+SOURCE+r"_(2026-\d{2})_([a-f0-9]{24})\.zip",f["name"])
            if match and match[1]==m["name"][:7]:output.append((match[1],f,match[2]))
    return output
def parse_ndc(d):
    original,h=load_sha_archived(d,"ndc_current_revised_source","zip")
    receipt_raw,_=load_sha_archived(d,"ndc_monthly_manifest","json")
    meta=json.loads(receipt_raw)
    if meta.get("native_zip_sha256")!=h:raise ValueError("NDC_NATIVE_ZIP_SHA")
    rows=[];seen=set()
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        if z.testzip():raise ValueError("NDC_ZIP_CRC")
        for filename in z.namelist():
            if not filename.lower().endswith(".xlsx"):continue
            content=z.read(filename);bsha=sha(content)
            wb=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
            for sheet in wb:
                for idx,r in enumerate(sheet.iter_rows(values_only=True),1):
                    if not any(v is not None and str(v).strip() for v in r):continue
                    cells=[v.isoformat() if isinstance(v,(dt.datetime,dt.date)) else str(v)
                           if v is not None else None for v in r]
                    key=(filename,sheet.title,idx)
                    if key in seen:raise ValueError("NDC_DUPLICATE_NATIVE_ROW")
                    seen.add(key)
                    rows.append(dict(source="NDC",workbook=filename,sheet=sheet.title,
                      row_index=idx,source_native_cells_json=json.dumps(cells,ensure_ascii=False),
                      native_workbook_sha256=bsha,source_zip_sha256=h,
                      observation_month_certified=False,published_at=None,pit_verified=False))
            wb.close()
    if not rows:raise ValueError("NDC_WORKBOOK_EMPTY")
    return rows,h
def main():
    if SOURCE not in SILVER:raise ValueError("IMMEDIATE_DOWNSTREAM_SOURCE_UNKNOWN")
    OUT.mkdir(exist_ok=True);d=service()
    done=[];reused=0;blocked=[];considered=0
    if SOURCE=="NDC":
        rows,h=parse_ndc(d)
        result=write_pair(d,SOURCE,"2026-09","OFFICIAL_G0_SHA_ARCHIVE",h,rows,[],
            "NDC_REVISED_NATIVE_CELLS")
        done.append(result)
    else:
        for month,f,prefix in candidate_files(d):
            if len(done)>=MAX_PER_RUN or considered>=MAX_PER_RUN*12:break
            considered+=1
            name=f["name"]
            sf=folder(d,SILVER[SOURCE],month+"_INCREMENTAL_CANDIDATE")
            recorded=ls(d,sf)
            if any(x["name"].startswith(f"V095_{SOURCE}_{month.replace('-','')}_{prefix[:20]}_SILVER_")
                   and x["name"].endswith(".parquet") for x in recorded):
                reused+=1;continue
            try:
                b=d.files().get_media(fileId=f["id"]).execute()
                digest=sha(b)
                if digest[:24]!=prefix:raise ValueError("BRONZE_ARCHIVE_SHA_FILENAME")
                validate_zip(b,SOURCE,month)
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    manifests=[x for x in z.namelist() if pathlib.PurePosixPath(x).name
                        in ("manifest.json","complement_manifest_R1.json")]
                    manifest=json.loads(z.read(manifests[0])) if manifests else {}
                    if SOURCE=="MOPS":sil,go,dataset=parse_mops(z,manifest,month,f["id"],digest)
                    elif SOURCE=="TDCC":sil,go,dataset=parse_tdcc(z,manifest,month,f["id"],digest)
                    else:sil,go,dataset=parse_taifex(z,month,f["id"],digest)
                done.append(write_pair(d,SOURCE,month,f["id"],digest,sil,go,dataset))
            except Exception as exc:
                blocked.append({"month":month,"source_archive_id":f["id"],
                    "sha_prefix":prefix,"reason":type(exc).__name__+":"+str(exc)[:110],
                    "state":"ADAPTER_PENDING_OR_SOURCE_QUARANTINE"})
                if len(blocked)>=12:break
    result={"source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),"candidate_files_examined":considered,
      "converted":done,"silver_converted":len(done),
      "gold_descriptive_created":sum(x.get("gold_id") is not None for x in done),
      "candidate_reused":reused,"blocked":blocked,"blocked_count":len(blocked),
      "run_bronze_incremental_independently":True,"whole_month_complete":False,
      "historical_PIT_certified":False,"Gold_400plus_certified":False}
    p=OUT/"result.json";p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":SOURCE,"silver_converted":len(done),
      "gold_descriptive_created":result["gold_descriptive_created"],
      "candidate_reused":reused,"blocked":len(blocked),
      "blocked_details":blocked[:4],"PIT":False},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
