#!/usr/bin/env python3
"""R17B targeted identical-path duplicate classification, READ ONLY.
Only public-safe counts are returned. Never change/delete v0.93 originals.
"""
import argparse,collections,json,pathlib,sys
from v098_r16_full_private_manifest import list_children,one_child
from v098_r11_six_source_metadata_pilot import service
SOURCES=("TWSE","TPEx")
def check(source,out):
    stats={"api_pages":0}
    result={"source":source,"status":"INIT","groups":0,"extra_file_entries":0,
      "same_content_groups":0,"different_content_groups":0,
      "same_size_different_hash_groups":0,
      "file_ids_unique":True,"production_migration_allowed":False}
    try:
        api=service()
        root=one_child(api,"root","ChatGPT資料存取",stats)
        v98=one_child(api,root,"C1_0.98",stats)
        rec=one_child(api,v98,"99_RECOVERY",stats)
        private=one_child(api,rec,"R16_PRIVATE_MANIFEST_TEST_ONLY",stats)
        files={f["name"]:f["id"] for f in list_children(api,private,stats)}
        for year in range(2000,2027):
            name=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
            if name not in files:raise RuntimeError("MISSING_MANIFEST")
            blob=api.files().get_media(fileId=files[name]).execute()
            pairs=collections.defaultdict(list)
            for line in blob.splitlines():
                if not line:continue
                r=json.loads(line)
                pairs[(r.get("parent_id"),r.get("filename"))].append(r)
            for group in pairs.values():
                if len(group)<2:continue
                result["groups"]+=1;result["extra_file_entries"]+=len(group)-1
                if len({r["file_id"] for r in group})<len(group):result["file_ids_unique"]=False
                hashes={(r.get("drive_md5"),r.get("size")) for r in group}
                if len(hashes)==1:result["same_content_groups"]+=1
                else:
                    result["different_content_groups"]+=1
                    if len({r.get("size") for r in group})==1:
                        result["same_size_different_hash_groups"]+=1
        result["status"]="PASS_CLASSIFIED_WITH_HOLD"
    except Exception as err:
        result["status"]="SCAN_ERROR";result["error_class"]=type(err).__name__
    finally:
        result["api_pages"]=stats["api_pages"]
        p=pathlib.Path(out);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    if result["status"]=="SCAN_ERROR":sys.exit(2)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=SOURCES)
    p.add_argument("--out",required=True);a=p.parse_args()
    check(a.source,a.out)
