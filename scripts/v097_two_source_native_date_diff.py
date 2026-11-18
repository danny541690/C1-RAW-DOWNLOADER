#!/usr/bin/env python3
"""Read-only matched-date TDCC/TAIFEX native differential audit.
Never upgrades formal G2 without identical date/identity official response bytes.
Writes immutable QA receipt and no Silver/Gold/Bronze mutations.
"""
import csv,hashlib,io,json,os,re,sys
from collections import Counter
from datetime import datetime,timezone
from html.parser import HTMLParser
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_two_source_pilot_g2 import kind
RUN=os.getenv("GITHUB_RUN_ID","manual")
VERSION="v097_g2_two_source_official_native_diff_r1"
TARGET_TDCC=[("20261008","2365"),("20261008","3258"),("20251107","2433")]
TARGET_TAIFEX_DAYS=["2024/01/02","2024/01/03","2024/01/04"]
TDCC_API="https://openapi.tdcc.com.tw/v1/opendata/1-5"
TAIFEX_OFFICIAL="https://www.taifex.com.tw/cht/3/largeTraderFutView"
TAIFEX_SOURCE_ID="1V3tY6CRlSB6JjOYld8sFPxmv2vDdg3tu"
MAX_BYTES=20*1024*1024
def sha(b):return hashlib.sha256(b).hexdigest()
def normalized(s):return re.sub(r"[\s\u3000（）()%％]+","",str(s).replace("\ufeff","")).lower()
class Table(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tables=[];self.on=False;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table":self.on=True;self.tables.append([])
        if tag=="tr" and self.on:self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:
            self.tables[-1].append(self.row);self.row=None
        if tag=="table":self.on=False
def tdcc_native(blob):
    t=Table();t.feed(blob.decode("utf-8-sig",errors="replace"))
    rows=next((x for x in t.tables if x and len(x[0])>=5 and "持股" in " ".join(x[0]) and "人數" in " ".join(x[0])),[])
    if not rows:return {"status":"MISSING_NATIVE_TABLE"}
    h=rows[0];data=[r[:5] for r in rows[1:] if len(r)>=5]
    output={"status":"NATIVE_PARSED","header":h,"data_rows":len(data),"first_three":data[:3],"last_two":data[-2:],
            "all_rows":data}
    if len(data) not in (16,17) or "合" not in data[-1][1]:
        output["status"]="UNKNOWN_TIER_LAYOUT";return output
    output["layout"]="HTML_15_TIERS_TOTAL" if len(data)==16 else "HTML_15_TIERS_ADJUSTMENT_TOTAL"
    try:
        sh=sum(int(x[3].replace(",","")) for x in data[:-1])
        total=int(data[-1][3].replace(",",""))
        output["native_shares_sum"]=sh;output["total_shares"]=total
        output["share_diff"]=sh-total
        output["total_holders"]=int(data[-1][2].replace(",",""))
        output["ratio_sum"]=round(sum(float(x[4].replace(",","")) for x in data[:-1]),3)
    except (ValueError,IndexError):output["status"]="NATIVE_VALUE_PARSE_HOLD"
    return output
def get_official_tdcc():
    try:
        import requests
        with requests.get(TDCC_API,timeout=(8,40),stream=True) as r:
            r.raise_for_status()
            blob=bytearray()
            for chunk in r.iter_content(262144):
                blob.extend(chunk)
                if len(blob)>MAX_BYTES:raise ValueError("OFFICIAL_LIMIT")
        raw=bytes(blob)
        try:d=json.loads(raw.decode("utf-8-sig"))
        except ValueError:
            import csv
            d=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        if isinstance(d,dict):
            for key in ("data","records","result"):
                if isinstance(d.get(key),list):d=d[key];break
        if not isinstance(d,list):return {"status":"OFFICIAL_NON_ROW_RESPONSE","raw_sha":sha(raw)},[]
        return {"status":"OFFICIAL_FETCHED","raw_sha":sha(raw),"rows":len(d)},d
    except Exception as e:return {"status":"OFFICIAL_FETCH_HOLD","type":type(e).__name__},[]
def tdcc_compare(api,call,rows):
    index={}
    for row in rows:
        path=row.get("source_path","")
        m=re.search(r"distribution_(\d{8})_([A-Za-z0-9]{4,8})",path)
        if m:index.setdefault((m.group(1),m.group(2).upper()),row)
    source, official=get_official_tdcc()
    def original_column(r,k):
        for field,value in r.items():
            if normalized(field)==normalized(k):return str(value).strip()
        return ""
    cases=[]
    for day,code in TARGET_TDCC:
        row=index.get((day,code))
        if not row:
            cases.append({"date":day,"security":code,"status":"BRONZE_SAMPLE_NOT_IN_COHORT"});continue
        raw=call(lambda:api.files().get_media(fileId=row["destination_id"]))
        a={"date":day,"security":code,"source_id":row["source_id"],
           "sha_match":sha(raw)==row["source_sha256"],"raw_sha":sha(raw)}
        native=tdcc_native(raw)
        a["native"]=native
        # Official live endpoint can be a different week; NEVER compare by code alone.
        same=[r for r in official if isinstance(r,dict) and
              original_column(r,"證券代號").strip().upper()==code and
              re.sub(r"\D","",original_column(r,"資料日期"))==day]
        seen=sorted({re.sub(r"\D","",original_column(r,"資料日期")) for r in official
                    if isinstance(r,dict) and original_column(r,"證券代號").strip().upper()==code})
        a["official"]=source
        a["official_same_date_rows"]=len(same)
        a["official_other_dates"]=seen[:10]
        if not a["sha_match"]:a["status"]="RAW_SHA_MISMATCH"
        elif native["status"]!="NATIVE_PARSED":a["status"]="NATIVE_LAYOUT_HOLD"
        elif not same:a["status"]="OFFICIAL_MATCHED_DATE_MISSING"
        else:
            # Match 1..15 and total 17 (if published) to native 1..15 + total 16.
            keyed={original_column(r,"持股分級").strip():r for r in same}
            compare=[]
            for r in native["all_rows"]:
                ordinal=int(r[0])
                official_ordinal=str(17 if ordinal==16 and native.get("layout")=="HTML_15_TIERS_TOTAL" else ordinal)
                official_row=keyed.get(official_ordinal)
                values=None if official_row is None else {
                    "holders":original_column(official_row,"人數"),
                    "shares":original_column(official_row,"股數"),
                    "ratio":original_column(official_row,"占集保庫存數比例%")}
                compare.append({"native_seq":ordinal,"official_seq":official_ordinal,
                                "native":r,"official":values,
                                "holders_shares_match":bool(values and
                                    values["holders"].replace(",","")==r[2].replace(",","") and
                                    values["shares"].replace(",","")==r[3].replace(",",""))})
            a["matched_date_rows"]=compare
            a["status"]="FULL_MATCHED_DATE_CANDIDATE" if all(x["holders_shares_match"] for x in compare) else "OFFICIAL_NATIVE_CELLS_DIFFER"
        cases.append(a)
    return {"official":source,"cases":cases}
def taifex_compare(api,call,rows):
    row=next((r for r in rows if r["source_id"]==TAIFEX_SOURCE_ID),None)
    if not row:return {"status":"TARGET_FROZEN_TAIFEX_SOURCE_ID_MISSING"}
    blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
    if sha(blob)!=row["source_sha256"]:return {"status":"RAW_SHA_MISMATCH"}
    encoding=None;rows_csv=None
    for enc in ("cp950","utf-8-sig","big5"):
        try:
            rows_csv=list(csv.reader(io.StringIO(blob.decode(enc))));encoding=enc;break
        except (UnicodeError,csv.Error):continue
    if rows_csv is None:return {"status":"CSV_DECODE_HOLD"}
    header=rows_csv[0] if rows_csv else []
    selected={}
    for day in TARGET_TAIFEX_DAYS:
        matches=[r for r in rows_csv[1:] if r and r[0].strip()==day]
        selected[day]={"count":len(matches),"first_three":matches[:3],
                       "widths":dict(Counter(len(r) for r in matches)),
                       "nonblank_tail":sum(bool(len(r)>len(header) and any(x.strip() for x in r[len(header):])) for r in matches)}
    notes=[r for r in rows_csv if r and r[0] and r[0].strip() not in TARGET_TAIFEX_DAYS and
           not re.fullmatch(r"\d{4}/\d{2}/\d{2}",r[0].strip())]
    return {"status":"ORIGINAL_NATIVE_THREE_DAYS_EXPOSED_OFFICIAL_MATCH_PENDING",
            "source_id":row["source_id"],"raw_sha":sha(blob),
            "official_dataset_url":TAIFEX_OFFICIAL,
            "encoding":encoding,"header":header,"total_rows":len(rows_csv),
            "days":selected,"non_date_rows_first_five":notes[:5],
            "note":"Historical official post download requires exact month/date response; landing-page HTML is not official numeric data."}
def run(source):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,source);assert_cohort(rows,source)
    evidence=tdcc_compare(api,call,rows) if source=="TDCC" else taifex_compare(api,call,rows)
    out={"schema":VERSION,"source":source,"run":RUN,"at":datetime.now(timezone.utc).isoformat(),
         "evidence":evidence,"g2_formal_pass":0,"bronze_modified":False,
         "silver_gold_materialized":False}
    rid=put_once(api,quality,"v097_TWO_SOURCE_NATIVE_DATE_DIFF_"+source+"_"+RUN+".json",out)
    upsert(api,control,"v097_TWO_SOURCE_NATIVE_DATE_DIFF_"+source+"_LATEST.json",
      {"schema":VERSION,"source":source,"run":RUN,"report_id":rid,
       "status":"OFFICIAL_COMPARE_CANDIDATE_NOT_G2_CERT"})
    print("TWO_SOURCE_DATE_DIFF="+canonical({"source":source,"run":RUN,"report_id":rid,
          "status":"RECORDED_NOT_FORMAL_G2"}),flush=True)
def selftest():
    assert len(TARGET_TDCC)==3 and len(TARGET_TAIFEX_DAYS)==3
    assert all(len(a)==8 and len(b)>=4 for a,b in TARGET_TDCC)
    s="<table><tr><th>序</th><th>持股/單位數分級</th><th>人數</th><th>股數/單位數</th><th>占集保庫存數比例 (%)</th></tr>"
    for i in range(1,17):
        s+="<tr><td>%d</td><td>%s</td><td>%d</td><td>%d</td><td>%s</td></tr>"%(i,"合 計" if i==16 else "tier",1 if i in (1,16) else 0,100 if i in (1,16) else 0,"100.00" if i in (1,16) else "0.00")
    test=tdcc_native((s+"</table>").encode())
    assert test["data_rows"]==16 and test["share_diff"]==0
    print("TWO_SOURCE_MATCHED_DATE_NATIVE_DIFF_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source" and sys.argv[2] in ("TDCC","TAIFEX"):run(sys.argv[2])
    else:raise SystemExit("selftest | source TDCC/TAIFEX")
