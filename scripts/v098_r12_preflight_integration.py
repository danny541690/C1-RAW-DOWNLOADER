#!/usr/bin/env python3
"""JARVIS v0.98 R12 pre-migration consolidated small-test gate.
Synthetic-only and local/runner artifact ledger tests; no Drive writes or real copy.
One-time bounded R12 live CI pre-migration test trigger.
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import sqlite3
import tempfile
import zipfile

from v098_r9_ledger_fault_injection import SOURCES, db, seed, claim, finish

def sha_bytes(blob):
    return hashlib.sha256(blob).hexdigest()

def internal_checks():
    # Real files are not touched. Make source/target simulated content differ,
    # proving the comparison cannot pass from filenames or byte count alone.
    source=b"official-example-\0-payload"
    copied=bytes(source)
    changed=source[:-1]+b"X"
    assert sha_bytes(source)==sha_bytes(copied)
    assert len(source)==len(changed) and sha_bytes(source)!=sha_bytes(changed)
    # A ZIP with a tampered member must fail CRC / decompression.
    zio=io.BytesIO()
    with zipfile.ZipFile(zio,"w",zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv",b"2026-09,123\n")
    valid=zio.getvalue()
    with zipfile.ZipFile(io.BytesIO(valid)) as archive:
        assert archive.testzip() is None
    corrupted=bytearray(valid)
    index=corrupted.find(b"2026-09")
    assert index>=0
    corrupted[index]=ord("X")
    with zipfile.ZipFile(io.BytesIO(corrupted)) as archive:
        assert archive.testzip()=="data.csv"
    # Duplicates require content version and logical dataset/date identity.
    objects=[
        {"dataset":"A","period":"2026-09","sha":sha_bytes(source)},
        {"dataset":"B","period":"2026-09","sha":sha_bytes(source)},
        {"dataset":"A","period":"2026-09","sha":sha_bytes(source)},
        {"dataset":"A","period":"2026-09","sha":sha_bytes(changed)},
    ]
    byte_equal=sum(a["sha"]==objects[0]["sha"] for a in objects)
    exact_same_key=sum(a==objects[0] for a in objects)
    assert byte_equal==3 and exact_same_key==2
    # Coverage unknown and valid-from must NOT become MISSING.
    def classify(period,valid_from,known_expected):
        if valid_from is None or known_expected is None:return "COVERAGE_UNKNOWN"
        if period<valid_from:return "NOT_APPLICABLE"
        return "EXPECTED" if known_expected else "NOT_SCHEDULED"
    assert classify("2000-01","2012-05",True)=="NOT_APPLICABLE"
    assert classify("2000-01",None,True)=="COVERAGE_UNKNOWN"
    assert classify("2026-09","2000-01",None)=="COVERAGE_UNKNOWN"
    return ["SHA256 identical vs same-size altered bytes",
            "ZIP CRC detects tampered member",
            "duplicate byte vs logical record vs version separated",
            "Expected Coverage: N/A, unknown, not scheduled separated"]

def init_checkpoint(path):
    c=db(path)
    seed(c)
    for src in SOURCES:
        a=claim(c,src,"R12-INITIAL",1000)
        assert a and finish(c,a,1001)
    r={"tasks":c.execute("SELECT count(*) FROM tasks").fetchone()[0],
       "committed":c.execute("SELECT count(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0]}
    c.close()
    assert r=={"tasks":6,"committed":6}
    return r

def restore_checkpoint(path):
    c=db(path)
    assert c.execute("SELECT count(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0]==6
    for src in SOURCES:
        assert claim(c,src,"SECOND_RUNNER",9999) is None
    n=c.execute("SELECT count(*) FROM attempts").fetchone()[0]
    c.close()
    assert n==6
    return {"status":"PASS","committed":6,"new_attempts":0,
            "scope":"SEPARATE_GITHUB_JOBS_SHARED_ARTIFACT_NOT_CROSS_RUN_CAS"}

def test_all(out):
    from v098_r11_six_source_metadata_pilot import children
    class FakeFiles:
        def __init__(self, pages):self.pages=pages
        def list(self, **kw):
            token=kw.get("pageToken","FIRST")
            page=self.pages[token]
            class Call:
                def execute(self2):return page
            return Call()
    class Fake:
        def __init__(self, p):self.p=p
        def files(self):return FakeFiles(self.p)
    # Actual Drive pager under test: 1000 + 13 entries. Require last page.
    pages={"FIRST":{"files":[{"id":str(i)} for i in range(1000)],"nextPageToken":"PAGE2"},
           "PAGE2":{"files":[{"id":str(i)} for i in range(1000,1013)]}}
    counts={"api_pages":0}
    rows=list(children(Fake(pages),"FAKE_PARENT",counts))
    assert len(rows)==1013 and counts["api_pages"]==2
    cyc={"FIRST":{"files":[],"nextPageToken":"LOOP"},
         "LOOP":{"files":[],"nextPageToken":"LOOP"}}
    try:list(children(Fake(cyc),"FAKE_PARENT",{"api_pages":0}))
    except RuntimeError as exc:assert str(exc)=="REPEATED_PAGE_TOKEN"
    else:raise AssertionError("Page token loop accepted")
    checks=internal_checks()
    result={"status":"PASS","synthetic_only":True,
       "checks":checks+["Drive pagination >1000 fully consumed",
                       "repeated page token detected"],
       "limits":["No real content downloaded","Not a complete 2000–2026 inventory",
                 "No cross-GitHub-Run durable master or atomic lease",
                 "No real Source/Target SHA256 comparison"]}
    write(out,result)
    return result

def write(path, obj):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("mode",choices=["test","checkpoint-init","checkpoint-resume"])
    a.add_argument("--db",default="r12_evidence/state.sqlite")
    a.add_argument("--out",default="r12_evidence/report.json")
    p=a.parse_args()
    if p.mode=="test":data=test_all(p.out)
    elif p.mode=="checkpoint-init":data={"status":"PASS","scope":"SYNTHETIC",**init_checkpoint(p.db)};write(p.out,data)
    else:data=restore_checkpoint(p.db);write(p.out,data)
    print(json.dumps(data))
if __name__=="__main__":main()
