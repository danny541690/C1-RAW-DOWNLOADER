#!/usr/bin/env python3
"""Bounded forensic probe for failed 2026 legacy source ZIP manifest variants.

Read-only: up to 5 official/legacy archives per source; only ZIP member metadata,
source/period fields, CRC and error codes; raw contents NEVER reclassified,
overwritten or promoted. Report goes to Drive with SHA readback.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib,zipfile,csv,re
from scripts.v095_2026_four_source_archive_intake import ls,validate_zip,digest
from scripts.v095_2026_prior_raw_reuse_audit import YEAR_PARENT
from scripts.v095_2026_annual_consolidated import service,FOLDER
from scripts.v095_market_release_calendar_drive_archive import archive,drive
OUT=pathlib.Path("v095_native_archive_probe")
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
def main():
    if SOURCE not in ("MOPS","TDCC","TAIFEX","NDC"):raise ValueError("INVALID_SOURCE")
    OUT.mkdir(exist_ok=True)
    d=service()
    max_probe=24 if SOURCE=="MOPS" else 5
    parents=[x for x in ls(d,YEAR_PARENT) if x["name"]==SOURCE and x["mimeType"]==FOLDER]
    if len(parents)!=1:raise ValueError("LEGACY_SOURCE_FOLDER_NOT_UNIQUE")
    issues=[];valid=[];scanned=0
    for m in range(1,12):
        month=f"2026-{m:02d}"
        children=[x for x in ls(d,parents[0]["id"]) if x["name"]==month and x["mimeType"]==FOLDER]
        if not children:
            issues.append({"month":month,"reason":"LEGACY_MONTH_FOLDER_NOT_FOUND"})
            continue
        if len(children)>1:raise ValueError("LEGACY_MONTH_DUPLICATE")
        for item in sorted(ls(d,children[0]["id"]),key=lambda z:z["name"]):
            if not item["name"].lower().endswith(".zip"):continue
            if scanned>=max_probe:break
            scanned+=1
            filehash=hashlib.sha256((item["id"]+item["name"]).encode()).hexdigest()[:18]
            record={"month_folder":month,"original_id_name_digest":filehash,
                    "source":SOURCE,"archive_bytes":int(item.get("size",0))}
            try:
                if record["archive_bytes"]>20_000_000:raise ValueError("ARCHIVE_TOO_LARGE")
                blob=d.files().get_media(fileId=item["id"]).execute()
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    record["zip_crc_ok"]=z.testzip() is None
                    record["member_count"]=len(z.infolist())
                    record["member_extensions"]=dict(collections.Counter(
                        pathlib.PurePosixPath(info.filename).suffix.lower() or "NO_EXTENSION"
                        for info in z.infolist() if not info.is_dir()))
                    record["manifest_paths"]=[info.filename for info in z.infolist()
                        if "manifest" in pathlib.PurePosixPath(info.filename).name.lower()][:5]
                    if SOURCE=="TDCC" and not record["manifest_paths"]:
                        record["sidecar_schema"]=[]
                        for member in z.infolist():
                            if member.is_dir() or member.file_size>2_000_000:continue
                            if member.filename.lower().endswith(".json"):
                                try:
                                    obj=json.loads(z.read(member))
                                    record["sidecar_schema"].append({
                                      "keys":sorted(str(k) for k in obj)[:20] if isinstance(obj,dict) else [],
                                      "source":obj.get("source") if isinstance(obj,dict) else None,
                                      "month":obj.get("month") if isinstance(obj,dict) else None,
                                      "period":obj.get("period") if isinstance(obj,dict) else None,
                                      "csv_sha256":obj.get("csv_sha256") if isinstance(obj,dict) else None,
                                      "sha256":obj.get("sha256") if isinstance(obj,dict) else None})
                                except Exception as e:record["sidecar_json_error"]=type(e).__name__
                            if member.filename.lower().endswith(".csv"):
                                try:
                                    raw=z.read(member)
                                    decoded=raw.decode("utf-8-sig",errors="replace")
                                    record["csv_sample_rows"]=[r[:12] for r in list(csv.reader(decoded.splitlines()[:5]))[:3]]
                                    record["csv_source_sha256"]=hashlib.sha256(raw).hexdigest()
                                except Exception as e:record["csv_schema_error"]=type(e).__name__
                    if SOURCE=="TAIFEX" and not record["manifest_paths"]:
                        from scripts.v093_taifex_independent import native_text
                        for member in z.infolist()[:2]:
                            if member.filename.lower().endswith(".csv") and member.file_size<3_000_000:
                                native=native_text(z.read(member))
                                lines=native.splitlines()
                                record["first_line_field_candidates"]=next(csv.reader(lines[:1]),[])[:22] if lines else []
                                record["first_lines_count"]=len(lines)
                                record["first_six_csv_rows"]=[row[:12] for row in list(csv.reader(lines[:10]))[:6]]
                                record["csv_first_line_numeric"]=sum(1 for v in record["first_line_field_candidates"] if re.fullmatch(r"[-+]?\\d+",v))
                    if len(record["manifest_paths"])==1:
                        name=record["manifest_paths"][0]
                        if z.getinfo(name).file_size<=500000:
                            try:
                                manifest=json.loads(z.read(name))
                                record["manifest_source"]=manifest.get("source")
                                record["manifest_month"]=manifest.get("month")
                                record["manifest_period"]=manifest.get("period")
                                record["manifest_keys"]=sorted(str(k) for k in manifest)[:14]
                                record["manifest_units_count"]=len(manifest.get("units",[]))
                                record["manifest_originals_count"]=len(manifest.get("immutable_originals",[]))
                                record["manifest_files_count"]=len(manifest.get("files",[]))
                                record["manifest_units_first"]=str(manifest.get("units",[])[:1])[:260]
                                record["manifest_files_first"]=str(manifest.get("files",[])[:1])[:260]
                            except Exception as ex:
                                record["manifest_metadata_error"]=type(ex).__name__
                validate_zip(blob,SOURCE,month)
                record["status"]="PASS_STRICT_MANIFEST_MEMBER_SHA"
                valid.append(record)
            except Exception as e:
                record["status"]="STRUCTURE_REVIEW_REQUIRED"
                record["reason"]=type(e).__name__+":"+str(e)[:95]
                issues.append(record)
        if scanned>=max_probe:break
    report={"source":SOURCE,"files_sampled":scanned,"strict_valid":len(valid),
       "structure_issues":len(issues),"issues":issues,"valid":valid,
       "no_original_data_promoted":True,"historical_source_pit_certified":False}
    path=OUT/f"{SOURCE.lower()}_legacy_manifest_probe.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    archive(d,path)
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
