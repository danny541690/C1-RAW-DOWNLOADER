#!/usr/bin/env python3
"""Read-only v0.93 archive candidate extraction for v0.95 OHLCV.

Prioritize validated original ZIP JSON bytes, without trusting file names alone.
Historical archive with ambiguous or unverified data is skipped and caller uses
the official source; never silently publishes a non-validated legacy member.
"""
import io
import json
import pathlib
import re
import zipfile
from scripts import v095_ultimate_r1_november_official as base
from scripts.v093_three_year_repair import validate

OLD_YEAR_ROOTS={"2025":"1VB9s43UHEQeZbPbLHOCcFAQewUDfjBOm",
                "2026":"1CAlRsbDEKTrb9BJlJ604SwYwQWRU3lpK"}
FOLDER="application/vnd.google-apps.folder"
MAX_ARCHIVES=14
MAX_ZIP_BYTES=20_000_000
MAX_NATIVE_BYTES=8_000_000

def legacy_snapshot(d,source,day,job):
    if source not in ("TWSE","TPEx") or day[:4] not in OLD_YEAR_ROOTS:return None
    src=[x for x in base.ls(d,OLD_YEAR_ROOTS[day[:4]]) if x["name"]==source and x.get("mimeType")==FOLDER]
    if len(src)!=1:return None
    month=[x for x in base.ls(d,src[0]["id"]) if x["name"]==day[:7] and x.get("mimeType")==FOLDER]
    if len(month)!=1:return None
    cat=job["category"]
    day_variants=(day,day.replace("-",""))
    files=[x for x in base.ls(d,month[0]["id"]) if
           x["name"].lower().endswith(".zip") and
           cat.lower() in x["name"].lower() and
           any(v in x["name"] for v in day_variants)]
    if len(files)>MAX_ARCHIVES:return None
    candidates=[]
    for f in files:
        # We never infer validity just because a filename matches the requested date.
        try:
            rawzip=d.files().get_media(fileId=f["id"]).execute()
            if len(rawzip)>MAX_ZIP_BYTES:continue
            with zipfile.ZipFile(io.BytesIO(rawzip)) as z:
                if z.testzip():continue
                members=[n for n in z.namelist() if n.lower().endswith(".json") and
                         not n.lower().endswith("manifest.json") and
                         not n.lower().endswith(".receipt.json")]
                for n in members:
                    info=z.getinfo(n)
                    if info.file_size>MAX_NATIVE_BYTES or ".." in pathlib.PurePosixPath(n).parts:continue
                    original=z.read(n)
                    try:
                        facts=validate(original,source,cat,day)
                        rows,unparsed=base.parse(original,source,day)
                        if len(rows)<300:continue
                    except (ValueError,KeyError,TypeError):
                        continue
                    candidates.append((original,facts,rows,unparsed))
        except (OSError,ValueError,zipfile.BadZipFile,RuntimeError):
            continue
    if len(candidates)!=1:
        # Multiple differing native candidates might be revised vintages; do not guess.
        return None
    raw,facts,rows,unparsed=candidates[0]
    return raw,facts,rows,unparsed,"VERIFIED_V093_NATIVE_ZIP_REUSE_NOT_PIT"
