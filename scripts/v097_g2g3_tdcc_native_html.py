#!/usr/bin/env python3
"""TDCC source-native HTML Dataset/Era metadata + full 17-tier shape audit.

Reads unmodified original HTML bytes; verifies body date/security independently
from HTML table columns and filename. NO official PIT/security classification,
no Silver/Gold output, and no implicit G2/G3/G4 certification.
"""
import datetime,hashlib,html,math,re,sys
from html.parser import HTMLParser
SOURCE="TDCC_HTML_BODY"
VERSION="tdcc_page_native_20261117_r1"
def metadata(blob,path=""):
    result={"source":SOURCE,"code":{"validated":False},"date":{"validated":False},
        "filename_consistent":None,"issues":[]}
    try: text=blob.decode("utf-8-sig")
    except UnicodeError:
        try:text=blob.decode("cp950")
        except UnicodeError:return {**result,"issues":["ENCODING_UNKNOWN"]}
    code=re.search(r"證券代號\s*[：:]\s*([A-Za-z0-9]{4,8})",text)
    date=re.search(r"資料日期\s*[：:]\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",text)
    if code:
        result["code"]={"value":code.group(1),"validated":True,"location":"HTML_BODY_TEXT"}
    else:result["issues"].append("STOCK_CODE_BODY_MISSING")
    if date:
        try:
            d=datetime.date(int(date.group(1))+1911,int(date.group(2)),int(date.group(3)))
            result["date"]={"value":d.isoformat(),"validated":True,"location":"HTML_BODY_TEXT"}
        except ValueError:result["issues"].append("DATE_INVALID")
    else:result["issues"].append("BODY_DATE_MISSING")
    f=re.search(r"distribution_(\d{8})_([A-Za-z0-9]{4,8})",path,re.I)
    if f and result["code"].get("validated") and result["date"].get("validated"):
        result["filename_consistent"]=(f.group(1)==result["date"]["value"].replace("-","") and
                                       f.group(2).upper()==result["code"]["value"].upper())
        if not result["filename_consistent"]:
            result["issues"].append("FILENAME_BODY_DATE_OR_SECURITY_CONFLICT")
            result["code"]["validated"]=False
            result["date"]["validated"]=False
    return result
class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.tables=[];self.table=False;self.row=False;self.cell=False
        self.cells=[];self.parts=[];self.current=[]
    def handle_starttag(self,name,attrs):
        if name=="table" and not self.table:self.table=True;self.rows=[]
        elif name=="tr" and self.table and not self.row:self.row=True;self.current=[]
        elif name in ("td","th") and self.row and not self.cell:
            self.cell=True;self.parts=[]
    def handle_data(self,data):
        if self.cell:self.parts.append(data)
    def handle_endtag(self,name):
        if name in ("td","th") and self.cell:
            self.current.append(" ".join("".join(self.parts).split()))
            self.cell=False
        elif name=="tr" and self.row:
            if self.current:self.rows.append(self.current)
            self.row=False
        elif name=="table" and self.table:
            if self.rows:self.tables.append(self.rows)
            self.table=False
def number(v):
    try:
        x=float(str(v).replace(",","").replace("%","").strip())
        return x if math.isfinite(x) else None
    except ValueError:return None
def inspect(blob,path):
    base={"schema":VERSION,"format":"TDCC_HTML","g2_verified":False,
          "g3_verified":False,"silver_schema_ready":False,"release":False,
          "official_pit_attested":False,"security_scope_attested":False}
    meta=metadata(blob,path)
    try:
        text=blob.decode("utf-8-sig")
    except UnicodeError:
        try:text=blob.decode("cp950")
        except UnicodeError:return {**base,"status":"ENCODING_HOLD","metadata":meta}
    parser=Tables();parser.feed(text)
    table=None
    for t in parser.tables:
        if not t:continue
        first="|".join(t[0])
        if ("持股" in first or "單位數分級" in first) and "人數" in first and "比例" in first:
            table=t;break
    if not table:return {**base,"status":"TDCC_DISTRIBUTION_TABLE_MISSING",
                         "metadata":meta,"table_count":len(parser.tables)}
    header=table[0];rows=table[1:]
    expected=("持股/單位數分級","人數","股數/單位數","占集保庫存數比例 (%)")
    if len(header)<5:return {**base,"status":"TDCC_TABLE_WIDTH_HOLD","metadata":meta,"header":header}
    problems=[];samples=[]
    for idx,row in enumerate(rows):
        if len(row)<5:
            problems.append("WIDTH_ROW_"+str(idx+1));continue
        t=number(row[0]);holders=number(row[2]);shares=number(row[3]);pct=number(row[4])
        if t is None or int(t)!=idx+1 or holders is None or shares is None or pct is None:
            problems.append("NATIVE_ROW_TYPE_"+str(idx+1));continue
        if holders<0 or shares<0 or pct<0 or pct>100.5:
            problems.append("NATIVE_ROW_RANGE_"+str(idx+1))
        samples.append({"tier":int(t),"holders":int(holders),"shares":int(shares),"percent":pct})
    if len(rows)!=17:problems.append("TDCC_EXPECTED_17_TIERS_ACTUAL_"+str(len(rows)))
    if len(samples)==17:
        # 16 is source-defined difference adjustment and 17 is total;
        # do not sum 1..17 or double count totals.
        subtotal=sum(v["shares"] for v in samples[:16])
        expected_total=samples[16]["shares"]
        difference=subtotal-expected_total
        if difference!=0:problems.append("TDCC_TIER_1_TO_16_VS_17_SHARES_DIFFER_"+str(difference))
        ratio=sum(v["percent"] for v in samples[:16])
        if abs(ratio-100)>0.2:problems.append("TDCC_TIER_PERCENT_SUM_DIFFER_"+str(round(ratio-100,5)))
    else:
        subtotal=None;expected_total=None;ratio=None
    if meta["issues"]:problems.extend(meta["issues"])
    status=("TDCC_NATIVE_NUMERIC_OR_METADATA_HOLD" if problems else
            "TDCC_FULL_NATIVE_LAYOUT_CANDIDATE_UNCERTIFIED")
    return {**base,"status":status,"metadata":meta,
        "observed_header":header,"data_rows":len(rows),"parsed_tiers":len(samples),
        "full_table_scanned":True,"checksum_tier_1_to_16":subtotal,"official_total_tier_17":expected_total,
        "percent_sum_1_to_16":ratio,"issues":problems}
def selftest():
    heading="<table><tr><th>序</th><th>持股/單位數分級</th><th>人數</th><th>股數/單位數</th><th>占集保庫存數比例 (%)</th></tr>"
    for i in range(1,18):
        heading+="<tr><td>%d</td><td>tier</td><td>%d</td><td>%d</td><td>%.1f</td></tr>"%(i,1 if i in (1,17) else 0,100 if i in (1,17) else 0,100 if i==1 else (100 if i==17 else 0))
    page=("<html><p>證券代號：4609</p><span>資料日期：114年11月28日</span>"+heading+"</table></html>").encode()
    m=metadata(page,"distribution_20251128_4609_x.html")
    assert m["code"]["validated"] and m["date"]["validated"] and m["filename_consistent"]
    x=inspect(page,"distribution_20251128_4609_x.html")
    assert x["status"]=="TDCC_FULL_NATIVE_LAYOUT_CANDIDATE_UNCERTIFIED"
    assert x["data_rows"]==17 and not x["g3_verified"]
    wrong=inspect(page,"distribution_20251127_4609_x.html")
    assert "FILENAME_BODY_DATE_OR_SECURITY_CONFLICT" in wrong["issues"]
    bad=inspect(page.replace(b"<td>100</td>",b"<td>101</td>",1),"distribution_20251128_4609_x.html")
    assert bad["status"]=="TDCC_NATIVE_NUMERIC_OR_METADATA_HOLD"
    assert inspect(b"<html>No data</html>","x.html")["status"]=="TDCC_DISTRIBUTION_TABLE_MISSING"
    print("TDCC_NATIVE_17_TIER_METADATA_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    else:raise SystemExit("selftest")
