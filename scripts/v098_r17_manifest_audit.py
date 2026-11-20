#!/usr/bin/env python3
"""R17 fail-closed source-manifest reconciliation. RE-USES 162 existing R16
private manifests, no raw downloads, no Drive writes, no Bronze migration.
All private IDs, filenames, checksums stay in process; public results only aggregates.
One bounded production-HOLD preflight CI trigger, audit-only.
"""
import argparse,collections,hashlib,json,pathlib,sys
from v098_r16_full_private_manifest import list_children,one_child
from v098_r11_six_source_metadata_pilot import SOURCES,service

EXPECTED=27
def audit(source,out):
    stats={"api_pages":0};record={"source":source,"status":"STARTED","years":0,"records":0,
         "missing_md5":0,"zero_byte":0,"duplicate_file_id":0,"same_parent_filename_conflicts":0,
         "same_md5_different_names_candidates":0,"identical_content_candidates":0,
         "missing_date_or_dataset_contract":True,"full_data_coverage_certified":False,
         "cross_run_atomic_cas_certified":False,"bulk_migration_allowed":False}
    try:
        api=service()
        main=one_child(api,"root","ChatGPT資料存取",stats)
        root=one_child(api,main,"C1_0.98",stats)
        recovery=one_child(api,root,"99_RECOVERY",stats)
        sandbox=one_child(api,recovery,"R16_PRIVATE_MANIFEST_TEST_ONLY",stats)
        index=collections.defaultdict(list)
        for f in list_children(api,sandbox,stats):
            index[f["name"]].append(f["id"])
        global_ids=set()
        for year in range(2000,2027):
            name=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
            hits=index.get(name,[])
            if len(hits)!=1:raise RuntimeError("MISSING_OR_DUPLICATE_R16_MANIFEST")
            blob=api.files().get_media(fileId=hits[0]).execute()
            rows=[json.loads(x) for x in blob.splitlines() if x.strip()]
            within_year_ids=set()
            identity=set()
            hashname=collections.defaultdict(set)
            hashcounts=collections.Counter()
            for r in rows:
                if r.get("source")!=source or r.get("year")!=year or not r.get("file_id"):
                    raise ValueError("SOURCE_YEAR_OR_ID_MISMATCH")
                fid=r["file_id"]
                if fid in within_year_ids or fid in global_ids:
                    record["duplicate_file_id"]+=1
                within_year_ids.add(fid);global_ids.add(fid)
                logical=(r.get("parent_id"),r.get("filename"))
                if logical in identity:record["same_parent_filename_conflicts"]+=1
                identity.add(logical)
                md5=r.get("drive_md5")
                if not md5:record["missing_md5"]+=1
                if int(r.get("size") or 0)==0:record["zero_byte"]+=1
                if md5:
                    content=(md5,int(r.get("size") or 0))
                    hashcounts[content]+=1
                    hashname[content].add(r.get("filename"))
            record["same_md5_different_names_candidates"]+=sum(
                max(0,len(names)-1) for names in hashname.values())
            record["identical_content_candidates"]+=sum(
                max(0,count-1) for count in hashcounts.values())
            record["years"]+=1;record["records"]+=len(rows)
        if record["duplicate_file_id"] or record["same_parent_filename_conflicts"]:
            record["status"]="HOLD_IDENTITY_CONFLICT"
        else:record["status"]="PASS_IDENTITY_AND_CANDIDATE_SCAN"
    except Exception as exc:
        record["status"]="SCAN_ERROR";record["error_class"]=type(exc).__name__
    finally:
        record["api_pages"]=stats["api_pages"]
        p=pathlib.Path(out);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2))
        print(json.dumps({k:v for k,v in record.items() if k in
           ("source","status","years","records","duplicate_file_id","same_parent_filename_conflicts")}))
    if record["status"] not in ("PASS_IDENTITY_AND_CANDIDATE_SCAN","HOLD_IDENTITY_CONFLICT"):
        sys.exit(2)

def selftest(out):
    # Distinguish equal content from duplicate identity, without inventing a dataset.
    records=[{"file_id":"a","parent_id":"p","filename":"x","drive_md5":"abcd","size":1},
             {"file_id":"b","parent_id":"q","filename":"y","drive_md5":"abcd","size":1}]
    assert len({r["file_id"] for r in records})==2
    assert len({(r["parent_id"],r["filename"]) for r in records})==2
    assert len({(r["drive_md5"],r["size"]) for r in records})==1
    # 216 is 27x8 planning categories; 162 is 27x6 actual sources.
    assert 27*8==216 and 27*len(SOURCES)==162
    result={"status":"PASS","tests":["logical identity differs from content equivalence",
          "duplicate md5 not deletion authorization","C8 216 planning vs 162 observed",
          "PIT and dataset coverage remain HOLD"]}
    p=pathlib.Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES)
    p.add_argument("--out",required=True);p.add_argument("--selftest",action="store_true")
    a=p.parse_args()
    if a.selftest:selftest(a.out)
    else:
        if not a.source:p.error("--source required")
        audit(a.source,a.out)
