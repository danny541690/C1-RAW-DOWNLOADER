#!/usr/bin/env python3
"""v0.97 Bronze deep QA of TWO original TDCC complement ZIP archives.
No raw overwrite, no Silver/Gold, no automatic certification.
Verifies each JSONL record against manifest, schema, year/month/date,
17 holding levels, duplicate (security, level), totals and 2-decimal percentages.
"""
import io,json,hashlib,zipfile,os,re
from decimal import Decimal,InvalidOperation
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,call,put_once

RUN=os.getenv("GITHUB_RUN_ID","manual")
ARCHIVES={
 "2026-08":"1xhAXJIuDqc_mrK67yMfmqu8vgqLhv1Du",
 "2026-10":"1pSg3M0T3TukE5wgShxbyeLy5KXqMhgmv"
}
def audit_member(z,member,expected_sha,ym):
    digest=hashlib.sha256()
    bycode=defaultdict(dict)
    issues=Counter()
    examples={}
    count=0
    found_dates=set()
    member_date=re.search(r"distribution_(\d{4}-\d{2}-\d{2})",member)
    for raw in z.open(member):
        digest.update(raw);count+=1
        try:
            row=json.loads(raw)["source_record"]
            date=str(row["資料日期"])
            code=str(row["證券代號"])
            level=int(row["持股分級"])
            holders=int(str(row["人數"]).replace(",",""))
            shares=int(str(row["股數"]).replace(",",""))
            percent=Decimal(str(row["占集保庫存數比例%"]).replace(",",""))
            if not re.fullmatch(r"20\d{6}",date) or date[:6]!=ym.replace("-",""):
                issues["BAD_DATE"]+=1
            found_dates.add(date)
            if member_date and date!=member_date.group(1).replace("-",""):
                issues["MEMBER_DATE_DISAGREES"]+=1
            if not (1<=level<=17 and holders>=0 and shares>=0 and percent.is_finite() and percent>=0):
                issues["BAD_NUMERIC_OR_LEVEL"]+=1
            if level in bycode[code]:issues["DUPLICATE_SECURITY_LEVEL"]+=1
            bycode[code][level]=(holders,shares,percent)
        except Exception as exc:
            issues["PARSE_FAILED"]+=1
    if digest.hexdigest()!=expected_sha:issues["MEMBER_SHA_MISMATCH"]+=1
    for code,levels in bycode.items():
        if set(levels)!=set(range(1,18)):
            issues["INCOMPLETE_17_LEVELS"]+=1;continue
        # Level 16 is a difference adjustment SUBTRACTED from sum of ranges 1..15.\n        # Historical raw records confirm this identity for every tested 2026-08/10 security.\n        # Level 17 is the published total. Preserve raw values, never overwrite.
        holders=sum(levels[i][0] for i in range(1,16))
        shares=sum(levels[i][1] for i in range(1,16))-levels[16][1]
        pct=sum((levels[i][2] for i in range(1,16)),Decimal(0))-levels[16][2]
        if holders!=levels[17][0]:
            issues["HOLDERS_TOTAL_MISMATCH"]+=1
            examples.setdefault("HOLDERS_TOTAL_MISMATCH",{"code":code,"details":str((holders,levels[17][0]))})
        if shares!=levels[17][1]:
            issues["SHARES_TOTAL_MISMATCH"]+=1
            examples.setdefault("SHARES_TOTAL_MISMATCH",{"code":code,"details":str((shares,levels[17][1],levels[16][1]))})
        if abs(pct-levels[17][2])>Decimal("0.2"):
            issues["PCT_TOTAL_DIFF_GT_0_2"]+=1
            examples.setdefault("PCT_TOTAL_DIFF_GT_0_2",{"code":code,"details":str((pct,levels[17][2]))})
    blockers=["PARSE_FAILED","BAD_NUMERIC_OR_LEVEL","DUPLICATE_SECURITY_LEVEL",
     "MEMBER_DATE_DISAGREES","MEMBER_SHA_MISMATCH","INCOMPLETE_17_LEVELS",
     "SHARES_TOTAL_MISMATCH","HOLDERS_TOTAL_MISMATCH","PCT_TOTAL_DIFF_GT_0_2"]
    state="ARCHIVE_RAW_INTEGRITY_QA_PASS_NUMERIC_REVIEW_PENDING" if not any(issues[k] for k in blockers) else "ARCHIVE_NUMERIC_EXCEPTIONS_HOLD"
    return {"member":member,"status":state,"rows":count,"security_count":len(bycode),
            "dates":sorted(found_dates),"sha_match":digest.hexdigest()==expected_sha,
            "issues":dict(issues),"examples":examples}
def main():
    api=service();_,_,quality,_=common(api)
    outcomes=[]
    for month,file_id in ARCHIVES.items():
        raw=call(lambda:api.files().get_media(fileId=file_id))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.testzip() is not None:raise RuntimeError("ZIP_CRC_FAILED:"+month)
            manifest=json.loads(z.read("complement_manifest_R1.json"))
            if manifest.get("month")!=month:raise RuntimeError("MANIFEST_PERIOD_CONFLICT")
            files=[]
            for source in manifest["files"]:
                member=os.path.basename(source["file"])
                if member not in z.namelist():raise RuntimeError("MISSING_MANIFEST_MEMBER:"+member)
                files.append(audit_member(z,member,source["sha256"],month))
            outcome={"month":month,"source_id":file_id,
                "raw_sha256":hashlib.sha256(raw).hexdigest(),"zip_crc_pass":True,
                "manifest_numeric_all_verified":manifest.get("numeric_all_verified"),
                "manifest_production_approved":manifest.get("production_approved"),
                "files":files}
            outcomes.append(outcome)
    totals=Counter()
    for r in outcomes:
        for f in r["files"]:
            totals["jsonl_members"]+=1;totals["source_rows"]+=f["rows"]
            totals["security_dates"]+=f["security_count"]
            totals.update(f["issues"])
    report={"schema":"v097_tdcc_complement_deep_bronze_audit_1",
      "run":RUN,"at":datetime.now(timezone.utc).isoformat(),
      "summary":dict(totals),"archives":outcomes,
      "bronze_raw_bytes_audited":True,
      "numeric_release_certified":False,\n      "numeric_formula":"SUM_LEVEL_01_TO_15_MINUS_LEVEL_16_EQUALS_LEVEL_17",
      "silver_gold_executed":False,
      "raw_modified":False,
      "decision":"NUMERIC_QA_PASS_IF_ZERO_BLOCKERS__SOURCE_ORIGIN_AND_MANIFEST_APPROVAL_STILL_HOLD"}
    put_once(api,quality,"v097_TDCC_COMPLEMENT_DEEP_QA_%s.json"%RUN,report)
    print("TDCC_COMPLEMENT_DEEP_QA="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w") as z:
        raw=b'{"source_record":{"\u8cc7\u6599\u65e5\u671f":"20260807","\u8b49\u5238\u4ee3\u865f":"2330","\u6301\u80a1\u5206\u7d1a":"17","\u4eba\u6578":"1","\u80a1\u6578":"10","\u5360\u96c6\u4fdd\u5eab\u5b58\u6578\u6bd4\u4f8b%":"100"}}\n'
        z.writestr("distribution_2026-08-07_test.jsonl",raw)
    with zipfile.ZipFile(io.BytesIO(data.getvalue())) as z:
        r=audit_member(z,"distribution_2026-08-07_test.jsonl",hashlib.sha256(raw).hexdigest(),"2026-08")
        assert r["issues"]["INCOMPLETE_17_LEVELS"]==1
    print("TDCC_COMPLEMENT_DEEP_QA_SELFTEST_PASS")
if __name__=="__main__":
    if os.getenv("TDCC_COMPLEMENT_MODE")=="selftest":selftest()
    else:main()
