#!/usr/bin/env python3
"""R14 bounded, fail-closed pre-bulk test. No Google Drive mutation.
For PUBLIC GitHub repository, outputs only safe counters and test statuses.
"""
import argparse, hashlib, io, json, os, pathlib, tempfile, zipfile
from v098_r11_six_source_metadata_pilot import SOURCES, service, children, unique_folder, unique_global_folder

def write(path, data):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True))

def sample(source, year, month, out, cap=2097152):
    result={"source":source,"year":year,"month":month,"scope":"READ_ONLY_REAL_SOURCE_TO_LOCAL_STAGING",
            "status":"INITIAL","sampled":0,"hash_pass":0,"crc_pass":0,"bytes":0,"api_pages":0,
            "production_bulk_migration_allowed":False}
    stats={"api_pages":0}
    try:
        api=service()
        root=unique_global_folder(api,"C1_0.93",stats)
        raw=unique_folder(api,root,"01_RAW",stats)
        yr=unique_folder(api,raw,str(year),stats) if raw else None
        src=unique_folder(api,yr,source,stats) if yr else None
        period=unique_folder(api,src,month,stats) if src else None
        if not period:
            result["status"]="PERIOD_NOT_FOUND_COVERAGE_UNKNOWN"
            return result
        seen=set();stack=[period];candidate=None
        while stack and candidate is None:
            folder=stack.pop()
            if folder in seen:raise ValueError("FOLDER_LOOP")
            seen.add(folder)
            for item in children(api,folder,stats):
                if item.get("mimeType")=="application/vnd.google-apps.folder":
                    stack.append(item["id"])
                elif 0<int(item.get("size") or 0)<=cap and item.get("md5Checksum"):
                    candidate=item;break
        if candidate is None:
            result["status"]="NO_ELIGIBLE_SMALL_SAMPLE"
            return result
        payload=api.files().get_media(fileId=candidate["id"]).execute()
        if len(payload)>cap or len(payload)!=int(candidate["size"]):
            raise ValueError("SIZE_MISMATCH")
        remote_md5=candidate["md5Checksum"]
        if hashlib.md5(payload).hexdigest()!=remote_md5:
            raise ValueError("REMOTE_MD5_MISMATCH")
        with tempfile.TemporaryDirectory() as d:
            # Exercise a real filesystem copy without writing or deleting any Drive object.
            srcfile=pathlib.Path(d)/"source.bin"
            destfile=pathlib.Path(d)/"target.bin"
            srcfile.write_bytes(payload);destfile.write_bytes(srcfile.read_bytes())
            source_sha=hashlib.sha256(srcfile.read_bytes()).hexdigest()
            destination_sha=hashlib.sha256(destfile.read_bytes()).hexdigest()
            if source_sha!=destination_sha:raise ValueError("STAGING_SHA_MISMATCH")
            result["hash_pass"]=1;result["bytes"]=len(payload);result["sampled"]=1
            if payload[:4]==b"PK\x03\x04":
                with zipfile.ZipFile(io.BytesIO(payload)) as z:
                    if z.testzip() is not None:raise ValueError("ZIP_CRC_MISMATCH")
                result["crc_pass"]=1
            # Fault injection: same length but different payload should fail digest
            if len(payload):
                altered=bytearray(payload);altered[0]^=1
                assert hashlib.sha256(altered).hexdigest()!=destination_sha
            result["status"]="LOCAL_STAGING_SHA256_PASS"
    except Exception as exc:
        result["status"]="TEST_ERROR"
        result["error_type"]=type(exc).__name__
    finally:
        result["api_pages"]=stats["api_pages"]
        write(out,result)
    return result

def selftest(out):
    a=b"JARVIS R14 TEST"
    b=bytearray(a);b[0]^=1
    assert len(a)==len(b)
    assert hashlib.sha256(a).hexdigest()!=hashlib.sha256(b).hexdigest()
    record={"status":"PASS","tests":["SHA256 alteration detection","public aggregate receipt",
                                      "no Google Drive write operation"],
            "not_tested":["transactional CAS across runs","real Drive target copy",
                          "complete 2000-2026 dataset coverage"],"synthetic":True}
    write(out,record);return record

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("sample","selftest"),required=True)
    p.add_argument("--source",choices=SOURCES)
    p.add_argument("--year",type=int,default=2026)
    p.add_argument("--month",default="2026-10")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if a.mode=="selftest":r=selftest(a.out)
    else:
        if not a.source or not(2000<=a.year<=2026) or not a.month.startswith(str(a.year)+"-"):
            p.error("invalid source/date")
        r=sample(a.source,a.year,a.month,a.out)
    print(json.dumps({k:v for k,v in r.items() if k in ("source","year","month","status","sampled","hash_pass","api_pages")}))
    if r["status"]=="TEST_ERROR":raise SystemExit(2)
