"""Isolated read-only audit of duplicate Drive names and historical boundary months.

No deletes, no overwrite, no automatic certification. Hashes only files <= 8 MiB.
"""
import collections,hashlib
from scripts.v093_standard_r1 import ROOT,SOURCES,ls
FOLDER="application/vnd.google-apps.folder"
MAX_HASH_BYTES=8_000_000

def audit_year(d,year,months=None,max_hash_bytes=MAX_HASH_BYTES):
    roots=[x for x in ls(d,ROOT) if x.get("name")==str(year) and x.get("mimeType")==FOLDER]
    if len(roots)!=1:raise ValueError("YEAR_FOLDER_MISSING_OR_AMBIGUOUS")
    srcfolders=ls(d,roots[0]["id"])
    report={"year":year,"months":{},"duplicates":[],"certified":False,"read_only":True}
    months=months or [f"{year}-{m:02d}" for m in range(1,13)]
    for source in SOURCES:
        src=[x for x in srcfolders if x.get("name")==source and x.get("mimeType")==FOLDER]
        if len(src)!=1:raise ValueError("SOURCE_FOLDER_MISSING_OR_AMBIGUOUS_"+source)
        srcmonths=ls(d,src[0]["id"])
        for month in months:
            folders=[x for x in srcmonths if x.get("name")==month and x.get("mimeType")==FOLDER]
            if len(folders)!=1:raise ValueError("MONTH_FOLDER_MISSING_OR_AMBIGUOUS_"+month)
            children=[x for x in ls(d,folders[0]["id"]) if x.get("mimeType")!=FOLDER]
            counter=collections.defaultdict(list)
            for f in children:counter[f["name"]].append(f)
            report["months"].setdefault(month,{})[source]={"files":len(children),"zip":sum(f["name"].lower().endswith(".zip") for f in children),"other":sum(not f["name"].lower().endswith(".zip") for f in children)}
            for name,group in counter.items():
                if len(group)<2:continue
                copies=[]
                for f in group:
                    item={"id":f["id"],"size":int(f.get("size",0)),"sha256":None}
                    if 0<item["size"]<=max_hash_bytes:
                        raw=d.call(lambda fid=f["id"]:d.api.files().get_media(fileId=fid))
                        if len(raw)!=item["size"]:raise ValueError("REMOTE_SIZE_MISMATCH")
                        item["sha256"]=hashlib.sha256(raw).hexdigest()
                    copies.append(item)
                hashes=[x["sha256"] for x in copies]
                status="IDENTICAL_CONTENT_NO_DELETE" if all(hashes) and len(set(hashes))==1 else ("DIFFERENT_CONTENT_QUARANTINE" if all(hashes) else "UNRESOLVED_LARGE_FILE_OR_EMPTY")
                report["duplicates"].append({"month":month,"source":source,"filename":name,"copies":copies,"status":status})
    return report
