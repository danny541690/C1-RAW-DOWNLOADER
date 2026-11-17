#!/usr/bin/env python3
"""V3 native header remediation: incremental QA-only, NEVER release or conversion."""
import collections,csv,hashlib,io,json,os,sys,zipfile
from html.parser import HTMLParser
from datetime import datetime,timezone
from scripts.v097_v3_preflight import SOURCES, read_baseline,assert_cohort,load_evidence,source_api,canonical
from scripts.v097_g2g3_contract_discovery import get_worker,analyse
from scripts.v097_v3_contract_registry import infer,REGISTRY_VERSION,CONTRACTS,normalize
from scripts.v097_v3_source_worker import fmt

VERSION="v097_g2g3_native_header_recovery_20261117_r1"
PARSER_REV="html_th_or_source_aliases_20261117_r3"
RUN=os.environ.get("GITHUB_RUN_ID","manual")
BATCH=max(1,min(65,int(os.environ.get("G2G3_HEADER_BATCH","30"))))
MAX_RAW=65*1024*1024
MAX_MEMBERS=5000
MAX_EXPAND=600*1024*1024
HEADER_PREFIX="v097_G2G3_HEADER_CK_"
def sha(b):return hashlib.sha256(b).hexdigest()
class HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.in_table=False;self.in_row=False;self.in_cell=False
        self.rows=[];self.row=[];self.row_had_th=False;self.table_row_types=[];self.cell=[];self.cell_tag="";self.tags=[]
    def handle_starttag(self,t,a):
        if t=="table" and not self.in_table and len(self.tables)<10:
            self.in_table=True;self.rows=[];self.table_row_types=[]
        elif t=="tr" and self.in_table and not self.in_row:self.in_row=True;self.row=[];self.row_had_th=False
        elif t in ("th","td") and self.in_row and not self.in_cell:
            self.in_cell=True;self.cell=[];self.cell_tag=t;self.row_had_th=self.row_had_th or t=="th"
    def handle_data(self,d):
        if self.in_cell:self.cell.append(d)
    def handle_endtag(self,t):
        if t in ("th","td") and self.in_cell:
            x=" ".join("".join(self.cell).split())
            self.row.append(x);self.tags.append(self.cell_tag)
            self.in_cell=False
        if t=="tr" and self.in_row:
            if self.row and len(self.rows)<8:
                self.rows.append(self.row);self.table_row_types.append(self.row_had_th)
            self.in_row=False
        if t=="table" and self.in_table:
            if self.rows:self.tables.append((self.rows,self.table_row_types))
            self.in_table=False
def header_for(blob,name,src=None):
    low=name.lower()
    if low.endswith((".htm",".html",".xml")) or b"<table" in blob[:10000].lower():
        for enc in ("utf-8-sig","cp950","big5"):
            try:
                h=HeaderParser();h.feed(blob[:3*1024*1024].decode(enc))
                aliases={normalize(a):field for fields in CONTRACTS.get(src,{}).values()
                    for field,values in fields.items() for a in values}
                def distinct_fields(row):
                    return len({aliases[normalize(x)] for x in row if normalize(x) in aliases})
                choices=[r for table,types in h.tables for r,has_th in list(zip(table,types))[:4]
                         if len(r)>1 and (has_th or distinct_fields(r)>=2)]
                if choices:return {"format":"HTML","header":max(choices,key=lambda r:(len(r),sum(len(x)>0 for x in r)))[:100],
                                   "tables_observed":len(h.tables),"encoding":enc,
                                   "status":"HEADER_OBSERVED_UNCERTIFIED"}
            except (UnicodeError,ValueError):pass
        return {"format":"HTML","header":[],"status":"HTML_TABLE_HEADER_PENDING"}
    if low.endswith(".csv") or low.endswith(".txt"):
        for enc in ("utf-8-sig","cp950","big5"):
            try:
                reader=csv.reader(io.StringIO(blob[:1024*1024].decode(enc)))
                rows=[r for _,r in zip(range(15),reader) if len(r)>1]
                if rows:return {"format":"CSV","header":max(rows,key=len)[:100],
                    "encoding":enc,"status":"HEADER_OBSERVED_UNCERTIFIED"}
            except (UnicodeError,csv.Error):pass
    if low.endswith(".jsonl"):
        try:
            found=[json.loads(line) for line in blob[:1024*1024].decode("utf-8-sig").splitlines()[:12] if line.strip()]
            dicts=[r for r in found if isinstance(r,dict)]
            if dicts:return {"format":"JSONL","header":list(dicts[0].keys())[:100],
                             "status":"HEADER_OBSERVED_UNCERTIFIED","observed_rows":len(dicts)}
        except (ValueError,UnicodeError):pass
        return {"format":"JSONL","header":[],"status":"JSONL_HEADER_PENDING"}
    if low.endswith(".json"):
        try:
            p=json.loads(blob.decode("utf-8-sig"))
            from scripts.v097_schema_gate_v2 import headers_from_json
            h=headers_from_json(p)
            if h:return {"format":"JSON","header":max(h,key=len)[:100],"status":"HEADER_OBSERVED_UNCERTIFIED"}
        except (ValueError,UnicodeError,TypeError):pass
    if low.endswith((".xlsx",".xlsm")):
        try:
            from openpyxl import load_workbook
            wb=load_workbook(io.BytesIO(blob),read_only=True,data_only=False)
            choices=[]
            for ws in wb.worksheets[:8]:
                for vals in ws.iter_rows(min_row=1,max_row=min(12,ws.max_row or 12),values_only=True):
                    h=[str(v).strip() for v in vals if v is not None]
                    if len(h)>1:choices.append((ws.title,h))
            wb.close()
            if choices:
                sheet,h=max(choices,key=lambda q:len(q[1]))
                return {"format":"XLSX","sheet":sheet,"header":h[:100],"status":"HEADER_OBSERVED_UNCERTIFIED"}
        except (OSError,ValueError,zipfile.BadZipFile,ImportError):pass
    return {"format":"OTHER","header":[],"status":"HEADER_UNRESOLVED"}
def inspect_native(blob,path,src,era):
    if fmt(path,blob)!="ZIP":
        evidence=[{"path":path,"sha":sha(blob),**header_for(blob,path,src)}]
    else:
        evidence=[]
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            members=[m for m in z.infolist() if not m.is_dir()]
            if len(members)>MAX_MEMBERS or sum(m.file_size for m in members)>MAX_EXPAND:
                return {"status":"ZIP_RESOURCE_LIMIT","members":len(members),"evidence":[]}
            for m in members:
                if m.filename.startswith("/") or ".." in m.filename.replace("\\","/").split("/"):
                    return {"status":"UNSAFE_ARCHIVE","evidence":[]}
                if m.file_size>8*1024*1024:
                    evidence.append({"path":m.filename,"status":"MEMBER_OVER_SAMPLE_LIMIT","header":[]})
                    continue
                content=z.read(m)
                evidence.append({"path":m.filename,"sha":sha(content),**header_for(content,m.filename,src)})
    for e in evidence:
        if e.get("header"):
            c=infer(src,e["header"],era)
            e["contract_candidate"]={"dataset":c.get("dataset_candidate"),
               "era_registered":c.get("era_registered"),"missing":c.get("missing_required"),
               "status":c["status"],"contract_registry":REGISTRY_VERSION,
               "g2_verified":False,"g3_verified":False}
    return {"status":"NATIVE_HEADERS_EXTRACTED_UNCERTIFIED",
            "evidence":evidence,"header_members":sum(bool(e.get("header")) for e in evidence)}
def source(src):
    if src not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
    pick,maps=load_evidence(api,control,match,load_json,src,rows)
    workers=get_worker(api,control,match,load_json,src,rows)
    name=HEADER_PREFIX+src+".json"
    f=match(api,control,name)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"done":{}}
    if ck.get("schema")!=VERSION:raise RuntimeError("HEADER_CHECKPOINT_VERSION_CONFLICT")
    done=ck["done"];new={}
    for row in rows:
        sid=row["source_id"];p=pick(row)
        if not p or row.get("bronze_status")!="BRONZE_INTEGRITY_READY":continue
        v=workers.get(sid);a=analyse(row,p,maps.get(sid),v)
        if a["g2g3_status"]!="HEADER_OR_ZIP_MEMBER_PENDING":continue
        prior=done.get(sid)
        if prior and prior.get("sha")==row["source_sha256"] and prior.get("schema")==VERSION:
            # Previously identified TH-based headers and all non-HTML evidence remain reusable.
            # Only results touched by the corrected HTML parser require invalidation.
            affected=any(e.get("format")=="HTML" for e in prior.get("evidence",[]))
            retry=prior.get("status")=="READ_OR_PARSE_PENDING" and prior.get("attempts",0)<3
            if (not affected or prior.get("parser_revision")==PARSER_REV) and not retry:
                continue
        if len(new)>=BATCH:break
        rec={"schema":VERSION,"parser_revision":PARSER_REV,"source_id":sid,"source":src,"sha":row["source_sha256"],
             "run":RUN,"historical_era":p.get("historical_version"),
             "silver_gold_executed":False,"g2_verified":False,"g3_verified":False}
        try:
            raw=call(lambda:api.files().get_media(fileId=row["destination_id"]))
            if not raw or len(raw)>MAX_RAW:rec["status"]="RAW_EMPTY_OR_SIZE_LIMIT"
            elif sha(raw)!=row["source_sha256"]:rec["status"]="SOURCE_SHA_MISMATCH"
            else:rec.update(inspect_native(raw,row["source_path"],src,p.get("historical_version")))
        except Exception as e:
            rec["status"]="READ_OR_PARSE_PENDING";rec["error_type"]=type(e).__name__
        if rec.get("status")=="READ_OR_PARSE_PENDING":
            rec["attempts"]=prior.get("attempts",0)+1 if prior else 1
            if rec["attempts"]>=3:rec["status"]="CONFIRMED_EXCEPTION_READ_FAILED"
        new[sid]=rec
    if new:
        rid=put_once(api,quality,"v097_G2G3_HEADER_DELTA_"+src+"_"+RUN+".json",
          {"schema":VERSION,"source":src,"run":RUN,"records":new})
        done.update(new);ck["done"]=done;ck["last_run"]=RUN
        ck["run_history"]=(ck.get("run_history",[])+[{"run":RUN,"delta_id":rid,"n":len(new)}])[-100:]
        upsert(api,control,name,ck)
        back=match(api,control,name)
        if not back or len(load_json(api,back["id"]).get("done",{}))!=len(done):
            raise RuntimeError("HEADER_CHECKPOINT_READBACK_MISMATCH")
    result={"run":RUN,"source":src,"checked_total":len(done),"new":len(new),
            "statuses":dict(collections.Counter(r.get("status") for r in done.values())),
            "members_with_header_total":sum(r.get("header_members",0) for r in done.values())}
    print("G2G3_NATIVE_HEADER_PROGRESS="+canonical(result),flush=True)
def selftest():
    b="<table><tr><th>證券代號</th><th>持股級距</th><th>人數</th></tr><tr><td>2330</td><td>1</td><td>200</td></tr></table>".encode()
    h=header_for(b,"tdcc.html")
    assert "證券代號" in h["header"] and "人數" in h["header"]
    misleading=header_for(b"<table><tr><td>2330</td><td>1</td><td>200</td></tr></table>","data.html")
    assert not misleading["header"],"Data-only HTML cannot be classified as header"
    td_head="<table><tr><td>StockNo</td><td>持股分級</td><td>人數</td></tr></table>".encode()
    assert "StockNo" in header_for(td_head,"tdcc.html","TDCC")["header"]
    assert header_for(b\'{"date":"2026-11-17","stock_id":"2330"}\\n\', "p.jsonl","FinMind")["header"]==["date","stock_id"]
    assert not header_for(b"<table><tr><td>2330</td><td>1</td><td>200</td></tr></table>","tdcc.html","TDCC")["header"]
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,"w") as z:z.writestr("a.html",b)
    p=inspect_native(mem.getvalue(),"a.zip","TDCC",None)
    assert p["header_members"]==1 and p["evidence"][0]["contract_candidate"]["g3_verified"] is False
    print("G2G3_NATIVE_HEADER_SAFETY_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source":source(sys.argv[2])
    else:raise SystemExit("selftest|source SOURCE")
