"""v0.95 migration gate: no production copying, reads files ONLY.

A Drive folder is not evidence of market-data coverage. Gate distinguishes
source bytes verified vs archived manifest-only, duplicates, CRC, bad paths,
unsafe inflation, and source version. Uses synthetic fixtures in CI; real
Drive copies require separate before/after SHA readback.
"""
import hashlib,io,json,pathlib,re,stat,unittest,zipfile
ALLOWED={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind","XQ"}
MAX_UNCOMPRESSED=1024*1024*1024
def verify_bytes(data,year,source,month,expected_sha):
    if source not in ALLOWED:return {"status":"REJECT_SOURCE"}
    if not re.fullmatch(r"20[0-2][0-9]",str(year)) or not (2000<=int(year)<=2026):
        return {"status":"REJECT_YEAR"}
    if not re.fullmatch(rf"{year}-(0[1-9]|1[0-2])",month):
        return {"status":"REJECT_MONTH"}
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected_sha:return {"status":"REJECT_SHA_MISMATCH","actual_sha256":actual}
    try:
        z=zipfile.ZipFile(io.BytesIO(data))
        names=z.infolist()
        if not names:return {"status":"REJECT_EMPTY_ARCHIVE"}
        total=0;seen=set();payloads=[]
        for x in names:
            n=x.filename.replace("\\","/")
            pure=pathlib.PurePosixPath(n)
            if n.startswith("/") or n.startswith("//") or ".." in pure.parts or ":" in n.split("/")[0]:
                return {"status":"REJECT_ARCHIVE_PATH_TRAVERSAL"}
            if stat.S_ISLNK(x.external_attr>>16):return {"status":"REJECT_SYMLINK"}
            if n in seen:return {"status":"REJECT_DUPLICATE_MEMBER"}
            seen.add(n);total+=x.file_size
            if total>MAX_UNCOMPRESSED:return {"status":"REJECT_INFLATION_LIMIT"}
            if not x.is_dir() and n.lower() not in ("manifest.json","readme.txt"):
                payloads.append(n)
        if z.testzip() is not None:return {"status":"REJECT_CRC"}
        if not payloads:
            return {"status":"QUARANTINE_MANIFEST_ONLY",
                    "archive_sha256":actual,"members":len(names),"payload_members":0}
        return {"status":"PASS_COPY_PREFLIGHT_ONLY","archive_sha256":actual,
                "members":len(names),"payload_members":len(payloads),
                "uncompressed_bytes":total,
                "bronze_approved":False,"silver_approved":False,
                "pit_verified":False}
    except (zipfile.BadZipFile,ValueError,RuntimeError,OSError):
        return {"status":"REJECT_INVALID_ARCHIVE"}
def mkzip(items):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,payload in items:z.writestr(name,payload)
    return out.getvalue()
class MigrationGateTests(unittest.TestCase):
    def test_good_archival_zip_still_not_bronze_approved(self):
        raw=mkzip([("prices_20261001.raw","DATA")])
        r=verify_bytes(raw,2026,"TWSE","2026-10",hashlib.sha256(raw).hexdigest())
        self.assertEqual(r["status"],"PASS_COPY_PREFLIGHT_ONLY")
        self.assertFalse(r["bronze_approved"])
    def test_manifest_only_not_data(self):
        raw=mkzip([("manifest.json",json.dumps({"units":[],"all_market_complete":False}))])
        self.assertEqual(verify_bytes(raw,2026,"MOPS","2026-10",hashlib.sha256(raw).hexdigest())["status"],
                         "QUARANTINE_MANIFEST_ONLY")
    def test_no_sha_mismatch(self):
        raw=mkzip([("a.csv","ok")])
        self.assertEqual(verify_bytes(raw,2026,"TWSE","2026-10","0"*64)["status"],
                         "REJECT_SHA_MISMATCH")
    def test_no_archive_zip_slip(self):
        raw=mkzip([("../steal.csv","bad")])
        self.assertEqual(verify_bytes(raw,2026,"TWSE","2026-10",hashlib.sha256(raw).hexdigest())["status"],
                         "REJECT_ARCHIVE_PATH_TRAVERSAL")
    def test_no_wrong_calendar_or_source(self):
        raw=mkzip([("a.csv","ok")]);s=hashlib.sha256(raw).hexdigest()
        self.assertEqual(verify_bytes(raw,2027,"TWSE","2027-01",s)["status"],"REJECT_YEAR")
        self.assertEqual(verify_bytes(raw,2026,"TWSE","2025-12",s)["status"],"REJECT_MONTH")
        self.assertEqual(verify_bytes(raw,2026,"UNAUTHORIZED","2026-10",s)["status"],"REJECT_SOURCE")
    def test_no_duplicate_zip_member(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw=mkzip([("same.csv","a"),("same.csv","b")])
        self.assertEqual(verify_bytes(raw,2026,"TWSE","2026-10",hashlib.sha256(raw).hexdigest())["status"],
                         "REJECT_DUPLICATE_MEMBER")
if __name__=="__main__":
    unittest.main(verbosity=2)
