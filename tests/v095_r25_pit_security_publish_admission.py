"""R25 one-pass real-data PIT/security-master and publisher admission audit.
Uses outputs of R17/R19/R20/R24 in the *same* runner. No publishing.
"""
import collections,datetime,hashlib,json,pathlib,re
import pyarrow.parquet as pq
ROOT=pathlib.Path("r25_integrated_admission")
ROOT.mkdir(exist_ok=True)
SOURCES=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
def read(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def parse_source_date(s):
    s=str(s).strip()
    if not re.fullmatch(r"\d{8}",s):return None
    try:return datetime.datetime.strptime(s,"%Y%m%d").date().isoformat()
    except ValueError:return None
def admit(item):
    # No guessing PIT from data date or current fetch time. Authenticated publisher
    # and independent upstream official security master must both be present.
    required=("source_sha256","silver_sha256","numeric_qa_signed","pit_release_signed",
              "official_security_master_signed","single_writer_fence_verified","rollback_receipt_signed")
    return all(item.get(k) is True if k not in ("source_sha256","silver_sha256")
               else isinstance(item.get(k),str) and len(item[k])==64 for k in required)
def main():
    legacy=read("r17_live_source_connectivity.json")
    r22=read("r22_combined/R22_RELEASE_GATE.json")
    gold=read("r24_tdcc_numeric_gold_candidate/report.json")
    r20=read("r20_tdcc_full/report.json")
    if set(r22["sources"])!=set(SOURCES):raise ValueError("SEVEN_SOURCE_MISMATCH")
    if gold["source_bronze_sha256"]!=r20["bronze_sha256"] or gold["source_silver_sha256"]!=r20["silver_sha256"]:
        raise ValueError("GOLD_TO_BRONZE_LINEAGE_MISMATCH")
    rows=pq.read_table("r24_tdcc_numeric_gold_candidate/tdcc_gold_qa_only.parquet").to_pylist()
    if len(rows)!=gold["security_date_groups"]:raise ValueError("TDCC_QA_GROUP_MISMATCH")
    classes=collections.Counter()
    dates=collections.Counter()
    excluded=collections.Counter()
    warnings=0
    for row in rows:
        code=row["security_id"]
        d=parse_source_date(row["source_date_raw"])
        if d is None:dates["UNKNOWN_SOURCE_DATE"]+=1
        else:dates[d]+=1
        # TDCC uses a six-character padded field, e.g. "2330  ".
        # Only trim right-side padding; NEVER remove leading zeroes or suffix letters.
        normalized=code.rstrip(" ")
        if re.fullmatch(r"\d{4}",normalized):
            classes["FOUR_DIGIT_CANDIDATE_NOT_MASTER_VERIFIED"]+=1
        else:
            classes["NON_FOUR_DIGIT_PRESERVE_RAW"]+=1
        if code!=normalized:classes["TRAILING_SPACE_PADDED_SOURCE_CODE"]+=1
        warnings+=bool(row["semantic_review_required"])
        if row["investment_gold_approved"] or row["pit_verified"] or row["security_master_verified"]:
            raise ValueError("UNVERIFIED_GOLD_IS_FALSLY_APPROVED")
        if admit(row):raise ValueError("UNSIGNED_CANDIDATE_RELEASED")
    # Build explicit negative tests for all seven release controls.
    good={"source_sha256":"a"*64,"silver_sha256":"b"*64,
          "numeric_qa_signed":True,"pit_release_signed":True,
          "official_security_master_signed":True,"single_writer_fence_verified":True,
          "rollback_receipt_signed":True}
    if not admit(good):raise AssertionError("VALID_SIGNED_FIXTURE_BLOCKED")
    checked=0
    for k in good:
        invalid=dict(good);invalid[k]=False if k.endswith("_signed") or k=="single_writer_fence_verified" else None
        if admit(invalid):raise AssertionError("MISSING_GATE_ALLOWED:"+k)
        checked+=1
    pub={s:{"sample_source_status":r22["sources"][s]["status"],
            "numeric_pit_signed":False,"official_security_master_signed":False,
            "complete_live_3layer":False if s!="TDCC" else True,
            "release_approved":False} for s in SOURCES}
    doc={"schema":"JARVIS_R25_PRELAUNCH_SIGNED_ADMISSION","release_approved":False,
         "status":"PASS_FAIL_CLOSED_QA",
         "seven_sources":pub,"tdcc_groups":len(rows),
         "tdcc_code_shape_counts":dict(classes),"tdcc_source_dates":dict(dates),
         "tdcc_semantic_warning_groups":warnings,
         "release_missing_control_rejections":checked,
         "drive_atomic_cas_verified":False,"publisher_credential_verified":False,
         "two_market_sessions_verified":False,
         "note":"4-digit code shape is not proof of TSE/OTC stock classification; raw date != public release timestamp."}
    (ROOT/"R25_SIGNED_ADMISSION_GATE.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    print("R25_TDCC_GROUPS="+str(len(rows))+" DATE_GROUPS="+str(len(dates))+
          " WARNINGS="+str(warnings))
    print("R25_CODE_SHAPES="+json.dumps(dict(classes)))
    print("R25_RELEASE_REQUIRED_CONTROLS_REJECTED="+str(checked))
    print("R25_RELEASE_APPROVED=false")
if __name__=="__main__":main()
