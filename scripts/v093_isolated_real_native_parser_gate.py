"""Read-only real Drive ZIP -> R2 native parser coverage test.

Never writes staging or labels any parsed cell verified.
"""
import collections,io,zipfile
from scripts.v093_isolated_historical_repair_inventory import inspect_month
from scripts.v093_standard_r1 import ROOT,SOURCES,ls
from scripts.v093_standard_r2 import parse
FOLDER="application/vnd.google-apps.folder"
def run(d,month,max_archive=10_000_000,max_member=1_000_000,max_members=12):
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
                    stats["oversize_skipped"]+=1
                    continue
                stats["members_attempted"]+=1
                try:
                    rows,invalid,encoding=parse(source,arc["name"],item.filename,z.read(item),month)
                    stats["native_cells_staged"]+=len(rows)
                    stats["invalid_rows"]+=invalid
                    stats["members_with_cells"]+=bool(rows)
                    stats["members_without_cells"]+=not bool(rows)
                except Exception as exc:
                    stats["parse_errors"]+=1
                    errors.append({"member":item.filename,"error":type(exc).__name__+":"+str(exc)[:120]})
        report["sources"][source]={"status":"REAL_NATIVE_PARSER_AUDITED_NOT_CERTIFIED","archive":arc["name"],"stats":dict(stats),"errors":errors[:10]}
    return report
