import hashlib,io,json,os,unittest,zipfile
os.environ.setdefault("V095_BRONZE_SOURCE","TDCC")
from scripts.v095_2026_four_source_archive_intake import validate_zip, load_quarantine_ledger
def pack(fmt,raw=b"original rows"):
    h=hashlib.sha256(raw).hexdigest()
    if fmt=="v093":
        m={"source":"MOPS","month":"2026-09","units":[{"file":"report.html","sha256":h}]}
        name="report.html"
    else:
        m={"source":"TDCC","period":"2026-09","immutable_originals":[{"archive_path":"original/001.raw","sha256":h}]}
        name="original/001.raw"
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr(name,raw)
        z.writestr("manifest.json",json.dumps(m))
    return b.getvalue()
class TestV095HistoricalNativeZIPManifest(unittest.TestCase):
 def test_quarantine_ledger_legacy_literal_backslash_n(self):
    sample=b'{"source":"MOPS","validator_version":"v1","immutable_zip_failures":{}}'
    self.assertEqual(load_quarantine_ledger(sample+b"\\\\n")["source"],"MOPS")
    self.assertEqual(load_quarantine_ledger(sample+b"\\n")["source"],"MOPS")
    with self.assertRaises(ValueError):load_quarantine_ledger(sample+b"{}")
    with self.assertRaises(ValueError):load_quarantine_ledger(sample+b"CORRUPT")
 def test_v093_hashed_unit(self):
    self.assertEqual(validate_zip(pack("v093"),"MOPS","2026-09"),1)
 def test_tdcc_exact_path_native(self):
    self.assertEqual(validate_zip(pack("tdcc"),"TDCC","2026-09"),1)
 def test_taifex_official_spread_order_title_row(self):
    text="期貨價差委託成交概況表,,,, \n交易日期,商品代號,價差委託成交量(B+S),市場總成交量(B+S),價差委託成交比率(%) \n20260909,BRF,0,672,0\n20260909,CAF,1146,13022,8.8\n"
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:f.writestr("20260909.csv",text.encode("utf-8-sig"))
    self.assertEqual(validate_zip(z.getvalue(),"TAIFEX","2026-09"),1)
    with self.assertRaises(ValueError):validate_zip(z.getvalue(),"TAIFEX","2026-10")
 def test_taifex_spread_invalid_ratio_rejected(self):
    text="期貨價差委託成交概況表,,,, \n交易日期,商品代號,價差委託成交量(B+S),市場總成交量(B+S),價差委託成交比率(%) \n20260909,CAF,1146,13022,99\n"
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:f.writestr("20260909.csv",text.encode("utf-8-sig"))
    with self.assertRaises(ValueError):validate_zip(z.getvalue(),"TAIFEX","2026-09")
 def test_mops_financial_manifest_without_root_source(self):
    raw=b"historical balance sheet original bytes"
    h=hashlib.sha256(raw).hexdigest()
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("financial.raw",raw)
        z.writestr("manifest.json",json.dumps({"numeric_verified":False,"pit_verified":False,
            "units":[{"source":"MOPS","month":"2026-03","file":"financial.raw","sha256":h}]}))
    self.assertEqual(validate_zip(b.getvalue(),"MOPS","2026-03"),1)
    with self.assertRaises(ValueError):validate_zip(b.getvalue(),"MOPS","2026-04")
 def test_tdcc_r1_complement_manifest(self):
    raw=b"<html>valid native tdcc stock data</html>"
    h=hashlib.sha256(raw).hexdigest()
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("source/snapshot.html",raw)
        z.writestr("complement_manifest_R1.json",json.dumps({"source":"TDCC",
            "month":"2026-09","files":[{"file":"snapshot.html","sha256":h}]}))
    self.assertEqual(validate_zip(b.getvalue(),"TDCC","2026-09"),1)
 def test_tdcc_r1_reject_invalid_hash(self):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("snapshot.html","original")
        z.writestr("complement_manifest_R1.json",json.dumps({"source":"TDCC",
            "month":"2026-09","files":[{"file":"snapshot.html","sha256":"a"*64}]}))
    with self.assertRaises(ValueError):validate_zip(b.getvalue(),"TDCC","2026-09")
 def test_source_and_month_are_not_interchangeable(self):
    with self.assertRaises(ValueError):validate_zip(pack("tdcc"),"MOPS","2026-09")
    with self.assertRaises(ValueError):validate_zip(pack("tdcc"),"TDCC","2026-10")
 def test_no_hashless_zip_promotions(self):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("original/001.raw",b"raw")
        z.writestr("manifest.json",json.dumps({"source":"TDCC","period":"2026-09",
        "immutable_originals":[{"archive_path":"original/001.raw"}]}))
    with self.assertRaises(ValueError):validate_zip(b.getvalue(),"TDCC","2026-09")
 def test_no_undeclared_members(self):
    b=io.BytesIO()
    raw=b"original rows"
    h=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("original/001.raw",raw)
        z.writestr("undocumented.csv","untrusted")
        z.writestr("manifest.json",json.dumps({"source":"TDCC","period":"2026-09",
        "immutable_originals":[{"archive_path":"original/001.raw","sha256":h}]}))
    with self.assertRaises(ValueError):validate_zip(b.getvalue(),"TDCC","2026-09")
if __name__=="__main__":unittest.main()
