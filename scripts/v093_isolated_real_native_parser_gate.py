"""Read-only real Drive ZIP -> R2 native parser coverage test.

Never writes staging or labels any parsed cell verified.
"""
import collections,io,json,zipfile,re
from html.parser import HTMLParser
from scripts.v093_isolated_historical_repair_inventory import inspect_month
from scripts.v093_standard_r1 import ROOT,SOURCES,ls
from scripts.v093_standard_r2 import parse
from scripts.v093_native_numeric_sanity import audit as native_audit
FOLDER="application/vnd.google-apps.folder"
def run(d,month,max_archive=12_000_000,max_member=5_000_000,max_members=12):
    y=[x for x in ls(d,ROOT) if x.get("name")==month[:4] and x.get("mimeType")==FOLDER]
    if len(y)!=1:raise ValueError("YEAR_AMBIGUOUS")
    sources={x["name"]:x for x in ls(d,y[0]["id"]) if x.get("mimeType")==FOLDER}
    report={"month":month,"sources":{},"certified":False,"drive_writes":0}
    for source in SOURCES:
        sf=sources.get(source)
        if sf is None:raise ValueError("SOURCE_MISSING_"+source)
        mf=[x for x in ls(d,sf["id"]) if x.get("name")==month and x.get("mimeType")==FOLDER]
        if len(mf)!=1:raise ValueError("MONTH_AMBIGUOUS_"+source)
        files=ls(d,mf[0]["id"])
        archives=sorted([x for x in files if x["name"].lower().endswith(".zip") and 0<int(x.get("size",0))<=max_archive],key=lambda x:x["name"])
        stats=collections.Counter()
        errors=[]
        zero_cell_diagnostics=[]
        oversize_members=[]
        if not archives:
            report["sources"][source]={"status":"NO_BOUNDED_ZIP_SAMPLE","stats":{},"errors":[]}
            continue
        arc=archives[0]
        raw=d.call(lambda:d.api.files().get_media(fileId=arc["id"]))
        if len(raw)>max_archive:raise ValueError("ARCHIVE_TOO_LARGE")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.testzip():raise ValueError("ZIP_CRC_FAILED")
            for item in z.infolist():
                if stats["members_attempted"]>=max_members:break
                if item.is_dir() or not item.filename.lower().endswith((".json",".raw",".jsonl",".csv")):continue
                if any(t in item.filename.lower() for t in ("manifest","receipt","checkpoint","metadata")):continue
                if item.file_size>max_member:
                    if len(oversize_members)<8:oversize_members.append({"member":item.filename,"uncompressed_bytes":item.file_size,"compressed_bytes":item.compress_size,"max_member_bytes":max_member})
                    stats["oversize_skipped"]+=1
                    continue
                stats["members_attempted"]+=1
                try:
                    rows,invalid,encoding=parse(source,arc["name"],item.filename,z.read(item),month)
                    sanity=native_audit(rows,month)
                    for field in ("invalid_date","invalid_stock_id","nonfinite_numeric","identifier_as_numeric","premature_verification","premature_publication","duplicate_lineage_key"):
                        stats["sanity_"+field]+=sanity[field]
                    stats["native_cells_staged"]+=len(rows)
                    stats["invalid_rows"]+=invalid
                    stats["members_with_cells"]+=bool(rows)
                    stats["members_without_cells"]+=not bool(rows)
                    if not rows and len(zero_cell_diagnostics)<4:
                        diag={"member":item.filename,"bytes":item.file_size,"encoding":encoding,"invalid_rows":invalid}
                        try:
                            payload=json.loads(z.read(item).decode("utf-8-sig"))
                            diag["payload_type"]=type(payload).__name__
                            if isinstance(payload,dict):
                                diag["top_level_keys"]=sorted(str(k) for k in payload)[:24]
                                if source=="TPEx" and isinstance(payload.get("tables"),list):
                                    diag["table_shapes"]=[]
                                    for t in payload["tables"][:3]:
                                        if not isinstance(t,dict):continue
                                        rows=t.get("data")
                                        fields=t.get("fields")
                                        shape={"title":str(t.get("title",""))[:70],"fields":[str(x)[:45] for x in fields[:25]] if isinstance(fields,list) else None,"rows":len(rows) if isinstance(rows,list) else None,"table_date":str(t.get("date",""))[:25]}
                                        if isinstance(rows,list) and rows:
                                            shape["first_row"]=([str(x)[:40] for x in rows[0][:25]] if isinstance(rows[0],list) else {str(k):str(v)[:40] for k,v in list(rows[0].items())[:20]} if isinstance(rows[0],dict) else str(type(rows[0]).__name__))
                                        diag["table_shapes"].append(shape)
                                data=payload.get("data",payload.get("rows"))
                                diag["data_rows"]=len(data) if isinstance(data,list) else None
                                if isinstance(data,list) and data and isinstance(data[0],dict):
                                    diag["row_keys"]=sorted(str(k) for k in data[0])[:24]
                        except (ValueError,UnicodeDecodeError):
                            diag["payload_type"]="NON_JSON_OR_UNDECODABLE"
                        zero_cell_diagnostics.append(diag)
                except Exception as exc:
                    stats["parse_errors"]+=1
                    entry={"member":item.filename,"error":type(exc).__name__+":"+str(exc)[:120]}
                    if source=="MOPS" and "HTML_NEEDS_DEDICATED_REVENUE_ADAPTER" in str(exc):
                        class Probe(HTMLParser):
                            def __init__(self):
                                super().__init__();self.tables=0;self.rows=0;self.cells=0;self.text=[]
                            def handle_starttag(self,tag,attrs):
                                if tag=="table":self.tables+=1
                                if tag=="tr":self.rows+=1
                                if tag in ("td","th"):self.cells+=1
                            def handle_data(self,data):
                                data=re.sub(r"\\s+"," ",data).strip()
                                if data and len(self.text)<30:self.text.append(data[:65])
                        p=Probe();p.feed(z.read(item).decode("utf-8","replace"))
                        entry["html_structure"]={"tables":p.tables,"rows":p.rows,"cells":p.cells,"text_preview":p.text}
                    errors.append(entry)
        report["sources"][source]={"status":"REAL_NATIVE_PARSER_AUDITED_NOT_CERTIFIED","archive":arc["name"],"stats":dict(stats),"errors":errors[:10],"zero_cell_diagnostics":zero_cell_diagnostics,"oversize_members":oversize_members}
    return report
