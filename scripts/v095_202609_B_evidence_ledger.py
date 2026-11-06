"""JARVIS 2026-09 B: immutable, fail-closed live Drive evidence ledger.

This is a canary for manifest/checkpoint/lineage, NOT a migration approval:
no old object is changed; source/Gold/PIT gaps remain BLOCKED.
"""
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import sys

OUT = Path("v095_202609_B_evidence")
MONTH = "2026-09"
EVIDENCE_PARENT = "1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
# Approved known September candidate IDs; live bytes are always checked.
CANDIDATES = {
    "Silver/TSE_PRICE": "14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz",
    "Silver/OTC_PRICE": "1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk",
    "Silver/MOPS_REVENUE": "1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5",
    "Silver/TDCC_WEEKLY": "1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r",
    "Silver/TSE_INSTITUTIONAL": "1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx",
    "Gold/TSE_PRICE": "1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI",
    "Gold/OTC_PRICE": "1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6",
    "Gold/MOPS_REVENUE": "1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI",
    "Gold/TSE_INSTITUTIONAL": "18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7",
    "Gold/OTC_CREDIT": "11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5",
}
GOLD_SILVER = {
    "Gold/TSE_PRICE": "Silver/TSE_PRICE",
    "Gold/OTC_PRICE": "Silver/OTC_PRICE",
    "Gold/MOPS_REVENUE": "Silver/MOPS_REVENUE",
    "Gold/TSE_INSTITUTIONAL": "Silver/TSE_INSTITUTIONAL",
}
def digest(data):
    return hashlib.sha256(data).hexdigest()

def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

def gate(row):
    """No inferential completion from job success, existence or byte size."""
    required = ("bytes_readback_verified", "schema_verified", "source_lineage_verified", "pit_verified", "formula_verified")
    return "ACCEPTED" if all(row.get(k) is True for k in required) else "BLOCKED"

def test():
    assert gate({"bytes_readback_verified": True}) == "BLOCKED"
    assert gate(dict.fromkeys(("bytes_readback_verified","schema_verified","source_lineage_verified","pit_verified","formula_verified"), True)) == "ACCEPTED"
    assert gate({"bytes_readback_verified": True, "schema_verified": True, "source_lineage_verified": False}) == "BLOCKED"
    print("SELF_TEST_PASS fail-closed", flush=True)

def drive():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    missing = [x for x in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN") if not os.environ.get(x)]
    if missing:
        raise RuntimeError("DRIVE_CREDENTIALS_MISSING:" + ",".join(missing))
    c = Credentials(token=None, refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"], client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request())
    return build("drive", "v3", credentials=c, cache_discovery=False)

def main():
    import pyarrow.parquet as pq
    from googleapiclient.http import MediaIoBaseUpload
    OUT.mkdir(exist_ok=True)
    run = os.environ.get("GITHUB_RUN_ID", "local")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    s = drive()
    entries = {}
    for label, fid in CANDIDATES.items():
        row = {"label":label, "drive_id":fid, "month":MONTH,
               "bytes_readback_verified":False, "schema_verified":False,
               "source_lineage_verified":False, "pit_verified":False,
               "formula_verified":False, "status":"BLOCKED"}
        try:
            metadata = s.files().get(fileId=fid,fields="id,name,mimeType,size,trashed").execute()
            if metadata.get("trashed"): raise ValueError("DRIVE_FILE_TRASHED")
            binary = s.files().get_media(fileId=fid).execute()
            if not binary: raise ValueError("EMPTY_DRIVE_OBJECT")
            if "size" in metadata and int(metadata["size"]) != len(binary):
                raise ValueError("DRIVE_BYTE_LENGTH_MISMATCH")
            row.update(file_name=metadata["name"], byte_count=len(binary),
                       sha256=digest(binary), bytes_readback_verified=True)
            if metadata.get("name","").lower().endswith(".parquet"):
                tab = pq.read_table(io.BytesIO(binary))
                row.update(schema_verified=True, row_count=tab.num_rows,
                           column_names=tab.column_names)
                if label.startswith("Gold/") and "input_silver_sha256" in tab.column_names:
                    row["declared_silver_sha256"] = sorted(
                        {str(x) for x in tab["input_silver_sha256"].to_pylist() if x})
            else:
                row["schema_issue"] = "NOT_PARQUET_VERIFY_SEPARATELY"
        except Exception as exc:
            row["error"] = type(exc).__name__ + ": " + str(exc)[:180]
        row["status"] = gate(row)
        entries[label] = row
    # Diagnose absent input_silver_sha256 separately from an actual bad checksum.
    # Do not treat source-native hashes as hashes of the Silver Parquet bytes.
    diagnostics_edges = []
    for gold, silver in GOLD_SILVER.items():
        g, sv = entries[gold], entries[silver]
        declarations = g.get("declared_silver_sha256", [])
        if not declarations:
            category = "MISSING_WHOLE_SILVER_SHA_DECLARATION"
        elif declarations == [sv.get("sha256")]:
            category = "EXACT_WHOLE_SILVER_SHA_MATCH"
        else:
            category = "DECLARED_SHA_DIFFERS_FROM_CURRENT_SILVER_BYTES"
        diag = {"gold":gold, "silver":silver, "classification":category,
                "silver_rows":sv.get("row_count"),"gold_rows":g.get("row_count"),
                "row_count_difference":(sv["row_count"]-g["row_count"]) if
                  isinstance(sv.get("row_count"), int) and isinstance(g.get("row_count"), int) else None,
                "repair":("ADD_VERIFIABLE_INPUT_VERSION_IN_NEXT_NONDESTRUCTIVE_GOLD_BUILD"
                  if category == "MISSING_WHOLE_SILVER_SHA_DECLARATION" else
                  "NO_SHA_REPAIR_REQUIRED" if category == "EXACT_WHOLE_SILVER_SHA_MATCH" else
                  "INVESTIGATE_SILVER_VERSION_AND_RECOMPUTE_ONLY_IF_PROVEN")}
        diagnostics_edges.append(diag)
    lineage = []
    for gold, silver in GOLD_SILVER.items():
        g, srow = entries[gold], entries[silver]
        declarations = g.get("declared_silver_sha256", [])
        matches = bool(srow.get("sha256") and declarations == [srow["sha256"]])
        lineage.append({"gold":gold, "silver":silver,
            "silver_sha256":srow.get("sha256"), "gold_sha256":g.get("sha256"),
            "gold_declared_input_sha256":declarations,
            "direct_silver_gold_sha_verified":matches,
            "bronze_input_proven":False, "pit_proven":False,
            "release":"BLOCKED"})
    # Treat lack of the original 0.93->0.95 SHA link as a real unresolved P0.
    p0 = {
        "release_fingerprint": "BLOCKED_REQUIRES_APPROVED_CODE_RETEST",
        "tdcc_durable_push": "UNVERIFIED",
        "publisher_cas_fencing": "UNVERIFIED",
        "ledger_durability": "CHECKPOINT_PUBLISHED_ONLY_IF_DRIVE_SHA_READBACK",
        "historical_pit": "UNVERIFIED",
        "actions_success_is_not_data_release": True,
    }
    manifest = {"schema":"JARVIS_V095_B_MANIFEST_V1","month":MONTH,
        "run_id":run,"created_utc":now,"candidates":entries,
        "bronze_v093_to_v095_byte_lineage":"NOT_CERTIFIED",
        "full_source_coverage":"NOT_CERTIFIED"}
    checkpoint = {"schema":"JARVIS_V095_B_CHECKPOINT_V1","run_id":run,
        "month":MONTH,
        "partition_states":{k: {"status":v["status"],"sha256":v.get("sha256"),
             "error":v.get("error")} for k,v in entries.items()},
        "publication":"BLOCKED",
        "canary_scope":len(entries),"approved_443":0}
    lineage_doc = {"schema":"JARVIS_V095_B_LINEAGE_V1","run_id":run,
        "edges":lineage,"all_443_indicators_certified":False,
        "actual_bronze_silver_gold_pit_release":False}
    diagnostics = {"schema":"JARVIS_V095_B_P0_V2","run_id":run,"p0":p0,
      "edges":diagnostics_edges,
      "release_fingerprint_root_cause":"v093 admission code_digest hashes every scripts/*.py and all workflow YAML; adding unrelated v095 workflow/scripts changes digest and blocks existing approved release. Do not bypass or rewrite tested_code_sha256 without complete approval.",
      "recommended_fix":"Create separately scoped v095 deployment attestation; keep legacy v093 release blocked pending full requalification."}
    payloads = {
        "manifest.json":manifest,"checkpoint.json":checkpoint,
        "lineage.json":lineage_doc,"p0_diagnostics.json":diagnostics
    }
    for filename, obj in payloads.items():
        (OUT / filename).write_bytes(encode(obj))
    # Never update existing files or claim commit before remote readback matches.
    receipts = {}
    for filename, obj in payloads.items():
        raw = encode(obj)
        name = "JARVIS_v095_B_202609_" + run + "_" + filename
        created = s.files().create(
            body={"name":name,"parents":[EVIDENCE_PARENT]},
            media_body=MediaIoBaseUpload(io.BytesIO(raw), mimetype="application/json",
                                         resumable=False), fields="id,name,size").execute()
        verified = s.files().get_media(fileId=created["id"]).execute()
        if digest(verified) != digest(raw):
            raise ValueError("DURABLE_READBACK_SHA_MISMATCH:" + filename)
        receipts[filename] = {"drive_id":created["id"],
            "sha256":digest(raw),"readback_verified":True}
    (OUT/"drive_receipts.json").write_bytes(encode(receipts))
    print(json.dumps({"run_id":run,
      "candidates":len(entries),
      "byte_verified":sum(v["bytes_readback_verified"] for v in entries.values()),
      "parquet_schema_verified":sum(v["schema_verified"] for v in entries.values()),
      "silver_gold_direct_sha_matches":sum(x["direct_silver_gold_sha_verified"] for x in lineage),
      "published_documents":len(receipts),
      "drive_readback_all":all(x["readback_verified"] for x in receipts.values()),
      "lineage_diagnoses":{x["gold"]:x["classification"] for x in diagnostics_edges},
      "formal_release":"BLOCKED_P0_BRONZE_PIT_443_NOT_CERTIFIED"},
      ensure_ascii=False),flush=True)

if __name__ == "__main__":
    if "--self-test" in sys.argv: test()
    else: main()
