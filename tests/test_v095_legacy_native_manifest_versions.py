import hashlib,io,json,os,unittest,zipfile
os.environ.setdefault("V095_BRONZE_SOURCE","TDCC")
from scripts.v095_2026_four_source_archive_intake import validate_zip
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
 def test_v093_hashed_unit(self):
    self.assertEqual(validate_zip(pack("v093"),"MOPS","2026-09"),1)
 def test_tdcc_exact_path_native(self):
    self.assertEqual(validate_zip(pack("tdcc"),"TDCC","2026-09"),1)
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
