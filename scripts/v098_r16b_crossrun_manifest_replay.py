#!/usr/bin/env python3
"""R16B: independent GitHub Run read-only replay of 162 PRIVATE R16 manifests.
Verifies all 27 per-source historical files were committed in Drive, readback
and parsed, with no duplicate file identities. Never uploads/modifies anything.
Source original remains untouched; public output is counters only.
Single bounded independent-run manifest replay invocation.
"""
import argparse,collections,hashlib,json,pathlib
from v098_r11_six_source_metadata_pilot import SOURCES,service
from v098_r16_full_private_manifest import roots,list_children
def main():
    p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES,required=True);p.add_argument("--out",required=True)
    a=p.parse_args();source=a.source;stats={"api_pages":0}
    r={"source":source,"mode":"CROSS_RUN_PRIVATE_READBACK_ONLY","status":"STARTED",
       "verified_manifests":0,"files":0,"years":0,"duplicate_ids":0,
       "new_files_created":0,"originals_modified":False,"bulk_migration_allowed":False}
    try:
        api=service();raw,sandbox=roots(api,stats)
        allfiles=list(list_children(api,sandbox,stats))
        byname=collections.defaultdict(list)
        for f in allfiles:byname[f["name"]].append(f)
        seen_global=set()
        for year in range(2000,2027):
            name=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
            matches=byname.get(name,[])
            if len(matches)!=1:raise RuntimeError("MISSING_OR_DUPLICATE_YEAR_MANIFEST")
            data=api.files().get_media(fileId=matches[0]["id"]).execute()
            rows=data.splitlines()
            for row in rows:
                item=json.loads(row)
                if item["source"]!=source or item["year"]!=year or item["content_verified"] or item["source_original_modified"]:
                    raise RuntimeError("INVALID_MANIFEST_ROW")
                key=item["file_id"]
                if key in seen_global:raise RuntimeError("CROSS_YEAR_DUPLICATE_FILE_ID")
                seen_global.add(key)
            r["verified_manifests"]+=1;r["files"]+=len(rows);r["years"]+=1
        r["status"]="PASS_CROSS_RUN_PRIVATE_MANIFEST_REPLAY"
    except Exception as exc:
        r["status"]="FAIL_CROSS_RUN_REPLAY";r["error_class"]=type(exc).__name__
    finally:
        r["api_pages"]=stats["api_pages"]
        q=pathlib.Path(a.out);q.parent.mkdir(parents=True,exist_ok=True)
        q.write_text(json.dumps(r,indent=2));print(json.dumps({k:r[k] for k in ("source","status","years","files","verified_manifests","new_files_created")}))
    if r["status"]!="PASS_CROSS_RUN_PRIVATE_MANIFEST_REPLAY":raise SystemExit(2)
if __name__=="__main__":main()
