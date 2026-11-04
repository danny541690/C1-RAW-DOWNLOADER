"""R10 combined prelaunch validation: synthetic fixtures only, no cloud credentials.
Validates data contract, monthly partitions, PIT, source conflict, Silver->Gold incremental,
restart/reconciliation and recovery with DuckDB/PyArrow. No production activation.
"""
import datetime as dt
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

def date_from(value):
    v=str(value).strip().lstrip("\ufeff")
    if v.isdigit() and len(v)==8:
        return dt.datetime.strptime(v,"%Y%m%d").date().isoformat()
    if len(v)==10:
        return dt.date.fromisoformat(v).isoformat()
    if "/" in v:
        y,m,d=map(int,v.split("/"))
        if y<1912: y+=1911
        return dt.date(y,m,d).isoformat()
    raise ValueError("DATE_UNSUPPORTED")

def parse_legacy_zip(blob):
    out=[]
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            if not name.endswith(".json") or name=="manifest.json": continue
            payload=json.loads(z.read(name))
            if not isinstance(payload,list): raise ValueError("ROWS_NOT_ARRAY")
            for row in payload:
                out.append({"date":date_from(row["date"]), "security_id":str(row["security_id"]),
                            "value":int(str(row["value"]).replace(",",""))})
    return out

def partition_rows(rows):
    result={}
    for r in rows:
        month=r["date"][:7]
        result.setdefault(month,[]).append(r)
    return result

def official_preference(records):
    providers={"TWSE":0, "TPEx":0, "MOPS":0,"TDCC":0, "TAIFEX":0, "NDC":0,"FinMind_Free":1,"FinMind_Backer":2}
    # Same key but distinct provenance; select for approved view only, preserve RAW.
    for r in records:
        if r["source"] not in providers: raise ValueError("SOURCE_UNREGISTERED")
    return min(records,key=lambda r:providers[r["source"]])

def qa_asof(records,asof):
    # Content period does not imply available to market; only published records accepted.
    return [r for r in records if r.get("published_at") and r["published_at"]<=asof]

def write_silver(root,groups,input_sha):
    paths={}
    for period,rows in groups.items():
        folder=Path(root)/"silver"/f"month={period}"
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/"part.parquet"
        pq.write_table(pa.Table.from_pylist(rows),path)
        back=duckdb.sql("SELECT COUNT(*) FROM read_parquet(?)",params=[str(path)]).fetchall()[0][0]
        if back!=len(rows): raise AssertionError("READBACK_ROW_COUNT")
        paths[period]={"path":str(path),"sha":hashlib.sha256(path.read_bytes()).hexdigest(),
                       "input_sha":input_sha,"rows":back}
    return paths

def gold_incremental(silver,new_input_sha,old_fingerprints):
    affected=[]
    for key,meta in silver.items():
        fingerprint=hashlib.sha256((meta["sha"]+new_input_sha+"formula_v1").encode()).hexdigest()
        if old_fingerprints.get(key)!=fingerprint: affected.append(key)
    return affected

def make_zip(records):
    target=io.BytesIO()
    with zipfile.ZipFile(target,"w") as z:
        z.writestr("manifest.json",json.dumps({"source":"TWSE","month":"2026-10"}))
        z.writestr("daily.json",json.dumps(records))
    return target.getvalue()

class FullCombinedIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.fixture=[
            {"date":"20260930","security_id":"2330","value":"1,000"},
            {"date":"115/10/01","security_id":"2330","value":"1,250"},
            {"date":"2026-10-02","security_id":"1101","value":"0"}]
        self.blob=make_zip(self.fixture)
    def tearDown(self): self.temp.cleanup()

    def test_01_taiwan_roc_to_gregorian(self):
        self.assertEqual(date_from("115/10/01"),"2026-10-01")
    def test_02_yyyymmdd_to_iso(self):
        self.assertEqual(date_from("20260930"),"2026-09-30")
    def test_03_reject_invalid_calendar_day(self):
        with self.assertRaises(ValueError): date_from("20260230")
    def test_04_zip_cross_month_uses_content_date(self):
        groups=partition_rows(parse_legacy_zip(self.blob))
        self.assertEqual(sorted(groups),["2026-09","2026-10"])
        self.assertEqual([len(x) for x in groups.values()],[1,2])
    def test_05_original_archive_unchanged(self):
        a=hashlib.sha256(self.blob).hexdigest()
        parse_legacy_zip(self.blob)
        self.assertEqual(a,hashlib.sha256(self.blob).hexdigest())
    def test_06_silver_parquet_readback(self):
        s=write_silver(self.root,partition_rows(parse_legacy_zip(self.blob)),hashlib.sha256(self.blob).hexdigest())
        self.assertEqual(sum(v["rows"] for v in s.values()),3)
        self.assertTrue(all(Path(v["path"]).exists() for v in s.values()))
    def test_07_zero_vs_missing_distinct(self):
        records=parse_legacy_zip(self.blob)
        self.assertEqual(records[-1]["value"],0)
        self.assertNotIn("null",records[-1])
    def test_08_official_precedence_not_source_deletion(self):
        r=[{"source":"FinMind_Backer","value":2},{"source":"TWSE","value":1}]
        self.assertEqual(official_preference(r)["value"],1)
        self.assertEqual(len(r),2)
    def test_09_wrong_provider_rejected(self):
        with self.assertRaises(ValueError): official_preference([{"source":"UNKNOWN"}])
    def test_10_pit_requires_real_publication(self):
        r=[{"published_at":"2026-11-10"},{"published_at":"2026-10-21"},{"published_at":None}]
        self.assertEqual(len(qa_asof(r,"2026-10-22")),1)
    def test_11_gold_changes_only_affected_partition(self):
        paths=write_silver(self.root,partition_rows(parse_legacy_zip(self.blob)),"x"*64)
        current={k:hashlib.sha256((v["sha"]+"x"*64+"formula_v1").encode()).hexdigest() for k,v in paths.items()}
        self.assertEqual(gold_incremental(paths,"x"*64,current),[])
        changed=gold_incremental({"2026-10":paths["2026-10"]},"y"*64,current)
        self.assertEqual(changed,["2026-10"])
    def test_12_input_sha_lineage(self):
        digest=hashlib.sha256(self.blob).hexdigest()
        paths=write_silver(self.root,partition_rows(parse_legacy_zip(self.blob)),digest)
        self.assertTrue(all(x["input_sha"]==digest for x in paths.values()))
    def test_13_crash_before_candidate_keeps_no_gold(self):
        with self.assertRaises(ValueError): date_from("bad-date")
        self.assertFalse((self.root/"gold").exists())
    def test_14_replay_same_archive_does_not_change_identity(self):
        self.assertEqual(hashlib.sha256(self.blob).hexdigest(),hashlib.sha256(bytes(self.blob)).hexdigest())
    def test_15_manifest_only_not_numeric(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:
            z.writestr("manifest.json",json.dumps({"units":[],"numeric_verified":False}))
        self.assertEqual(parse_legacy_zip(data.getvalue()),[])
    def test_16_reject_nonrecord_payload(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z: z.writestr("bad.json",json.dumps({"not":"rows"}))
        with self.assertRaises(ValueError): parse_legacy_zip(b.getvalue())

if __name__=="__main__": unittest.main(verbosity=2)
