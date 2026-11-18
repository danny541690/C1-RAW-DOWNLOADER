"""JARVIS R3: fail-closed formal contract and release ledger kernel.

No data-plane writes. All proof inputs must originate from evidence registries,
not parser inference. The staging tests exercise this same deterministic logic.
"""
from __future__ import annotations
import hashlib, json, re
from collections import Counter
from datetime import date
from scripts.v097_r3_gate_core import SOURCES, COHORT, GATES, digest, evidence_key

COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,
        "TAIFEX":3140,"NDC":320,"FinMind":3700}
HEX=re.compile(r"^[0-9a-fA-F]{64}$")
PASS={"PASS","REUSED_PASS"}

def require_sha(value,label):
    if not isinstance(value,str) or not HEX.fullmatch(value):
        raise ValueError("BAD_"+label)
    return value.lower()

def certified_contract(proof, row):
    """G2 official per-dataset historical contract: cannot rely on candidate registry."""
    if not isinstance(proof,dict):return {"status":"HOLD","reason":"G2_MISSING_OFFICIAL_CERT"}
    required=("source","source_id","content_sha256","dataset","template_id",
              "start_date","end_date","official_reference","official_evidence_id",
              "contract_version","required_fields","approved_aliases",
              "publication_asof_verified","official_attested")
    if any(k not in proof for k in required):return {"status":"HOLD","reason":"G2_INCOMPLETE_OFFICIAL_CERT"}
    try:
        if proof["source"]!=row["source"] or proof["source_id"]!=row["source_id"]:
            raise ValueError("IDENTITY")
        if require_sha(proof["content_sha256"],"CONTRACT_SHA")!=require_sha(row["source_sha256"],"SOURCE_SHA"):
            raise ValueError("SHA_CHANGED")
        effective=date.fromisoformat(str(row["data_date"])[:10])
        begin=date.fromisoformat(proof["start_date"])
        end=date.fromisoformat(proof["end_date"])
        if not begin<=effective<=end:raise ValueError("HISTORICAL_ERA_MISMATCH")
        if not isinstance(proof["required_fields"],list) or not proof["required_fields"]:
            raise ValueError("NO_REQUIRED_FIELDS")
        if len(proof["required_fields"])!=len(set(proof["required_fields"])):
            raise ValueError("DUPLICATE_REQUIRED_FIELDS")
        if not isinstance(proof["approved_aliases"],dict):
            raise ValueError("BAD_ALIAS_REGISTRY")
        if proof["official_attested"] is not True or proof["publication_asof_verified"] is not True:
            raise ValueError("OFFICIAL_AND_PIT_UNVERIFIED")
        if not all(isinstance(proof[k],str) and proof[k].strip() for k in
                   ("dataset","template_id","official_reference","official_evidence_id","contract_version")):
            raise ValueError("OFFICIAL_REFERENCE_MISSING")
    except (ValueError,KeyError,TypeError) as exc:
        return {"status":"HOLD","reason":"G2_"+str(exc)}
    return {"status":"PASS","dataset":proof["dataset"],"template_id":proof["template_id"],
            "contract_version":proof["contract_version"],"required_fields":list(proof["required_fields"]),
            "approved_aliases":dict(proof["approved_aliases"]),"proof_digest":digest(proof)}

def validate_g3(proof,row,g2):
    """Full-file native parse must prove all required source semantics and typed keys."""
    if g2.get("status")!="PASS":return {"status":"HOLD","reason":"G3_UPSTREAM_G2"}
    if not isinstance(proof,dict):return {"status":"HOLD","reason":"G3_MISSING_NATIVE_CERT"}
    mandatory=("source_id","content_sha256","dataset","g2_contract_version",
               "full_file_scanned","native_units_verified","types_and_keys_verified",
               "row_count","validation_errors","observed_fields","parser_version",
               "independent_evidence_id")
    if any(k not in proof for k in mandatory):return {"status":"HOLD","reason":"G3_INCOMPLETE"}
    if (proof["source_id"]!=row["source_id"] or proof["content_sha256"]!=row["source_sha256"]
        or proof["dataset"]!=g2["dataset"] or proof["g2_contract_version"]!=g2["contract_version"]):
        return {"status":"HOLD","reason":"G3_IDENTITY_OR_VERSION_MISMATCH"}
    if any(proof[k] is not True for k in ("full_file_scanned","native_units_verified","types_and_keys_verified")):
        return {"status":"HOLD","reason":"G3_FULL_NATIVE_UNVERIFIED"}
    if not isinstance(proof["row_count"],int) or proof["row_count"]<=0 or proof["validation_errors"]!=0:
        return {"status":"HOLD","reason":"G3_DATA_QUALITY"}
    fields=proof["observed_fields"]
    if not isinstance(fields,list) or not fields or len(set(fields))!=len(fields):
        return {"status":"HOLD","reason":"G3_DUPLICATE_OR_MISSING_FIELDS"}
    if not proof["independent_evidence_id"] or not proof["parser_version"]:
        return {"status":"HOLD","reason":"G3_EVIDENCE_MISSING"}
    # The FULL native proof must cover every dataset-era required semantic,
    # not merely report an arbitrary well-formed header.
    required=set(g2["required_fields"])
    aliases=g2["approved_aliases"]
    resolved=[aliases.get(x,x) for x in fields]
    if len(set(resolved))!=len(resolved) or not required.issubset(set(resolved)):
        return {"status":"HOLD","reason":"G3_G2_REQUIRED_SEMANTICS_UNATTESTED"}
    return {"status":"PASS","parser_version":proof["parser_version"],
            "verified_fields":sorted(set(resolved)),"proof_digest":digest(proof)}

def validate_g4(mapping,row,g2,g3):
    """Dry Silver INPUT only. Never construct Silver rows or tables."""
    if g2.get("status")!="PASS" or g3.get("status")!="PASS":
        return {"status":"HOLD","reason":"G4_UPSTREAM_G2_G3"}
    if not isinstance(mapping,dict):return {"status":"HOLD","reason":"G4_MISSING_MAPPING_CERT"}
    required=("source_id","content_sha256","dataset","g2_contract_version",
              "g3_parser_version","mapping_version","target_fields",
              "units_verified","time_basis_verified","security_identity_asof_verified",
              "numeric_semantics_verified","independent_evidence_id","materialized")
    if any(k not in mapping for k in required):return {"status":"HOLD","reason":"G4_INCOMPLETE"}
    if (mapping["source_id"]!=row["source_id"] or mapping["content_sha256"]!=row["source_sha256"]
        or mapping["dataset"]!=g2["dataset"] or
        mapping["g2_contract_version"]!=g2["contract_version"] or
        mapping["g3_parser_version"]!=g3["parser_version"]):
        return {"status":"HOLD","reason":"G4_IDENTITY_OR_DEPENDENCY_MISMATCH"}
    if not isinstance(mapping["target_fields"],dict) or not mapping["target_fields"]:
        return {"status":"HOLD","reason":"G4_TARGET_FIELDS_MISSING"}
    if len(set(mapping["target_fields"].values()))!=len(mapping["target_fields"]):
        return {"status":"HOLD","reason":"G4_DUPLICATE_TARGET_FIELDS"}
    if not set(mapping["target_fields"]).issubset(set(g3["verified_fields"])):
        return {"status":"HOLD","reason":"G4_SOURCE_FIELDS_NOT_IN_G3_PROOF"}
    if any(mapping[k] is not True for k in ("units_verified","time_basis_verified",
                                           "security_identity_asof_verified","numeric_semantics_verified")):
        return {"status":"HOLD","reason":"G4_SEMANTICS_OR_PIT_UNVERIFIED"}
    if mapping["materialized"] is not False:return {"status":"HOLD","reason":"G4_UNAUTHORIZED_SILVER_MATERIALIZATION"}
    if not mapping["mapping_version"] or not mapping["independent_evidence_id"]:
        return {"status":"HOLD","reason":"G4_EVIDENCE_MISSING"}
    return {"status":"PASS","mapping_version":mapping["mapping_version"],"proof_digest":digest(mapping)}

def certificate(row, gates, proofs, *, writer_fence, durable_readback, schema="R3_G5_CERT_V1"):
    """G5 requires actual chain, prior committed gate receipts and fenced sole writer."""
    if not writer_fence or not durable_readback:
        return {"status":"HOLD","reason":"G5_WRITER_FENCE_OR_READBACK_PENDING"}
    if any(gates.get(g) not in PASS for g in ("G1","G2","G3","G4")):
        return {"status":"HOLD","reason":"G5_UNPASSED_UPSTREAM"}
    if any(not isinstance(proofs.get(g),dict) or not proofs[g].get("independent_evidence_id")
           or not proofs[g].get("durably_committed") is True
           or not HEX.fullmatch(str(proofs[g].get("evidence_sha256","")))
           for g in ("G1","G2","G3","G4")):
        return {"status":"HOLD","reason":"G5_GATE_EVIDENCE_NOT_DURABLE"}
    attestation={
        "schema":schema,"source_id":row["source_id"],"source":row["source"],
        "source_sha256":require_sha(row["source_sha256"],"RECORD_SHA"),
        "dependencies":{g:proofs[g]["evidence_sha256"].lower() for g in ("G1","G2","G3","G4")},
        "writer_fence":writer_fence,"status":"SILVER_READY","silver_materialized":False,
        "gold_materialized":False
    }
    # This is only the PRE-COMMIT candidate. Actual PASS requires Drive readback.
    return {"status":"CANDIDATE","certificate":attestation,"certificate_sha256":digest(attestation)}

def confirm_g5_readback(candidate, actual):
    """Only an independently fetched exact Drive document promotes a candidate."""
    if not isinstance(candidate,dict) or candidate.get("status")!="CANDIDATE":
        return {"status":"HOLD","reason":"G5_NO_VALID_CANDIDATE"}
    if not isinstance(actual,dict) or digest(actual)!=candidate.get("certificate_sha256") or actual!=candidate.get("certificate"):
        return {"status":"HOLD","reason":"G5_REMOTE_READBACK_MISMATCH"}
    return {"status":"PASS","certificate_sha256":candidate["certificate_sha256"]}

def full_reconcile(records,expected_counts=COUNTS,*,baseline=None,require_baseline=False):
    """Reject missing, duplicate, cross-source, invalid or premature READY records."""
    if len(records)!=COHORT:raise ValueError("FROZEN_74750_MISSING_OR_EXTRA")
    if len({r["source_id"] for r in records})!=COHORT:raise ValueError("DUPLICATE_SOURCE_ID")
    if require_baseline and not isinstance(baseline,dict):
        raise ValueError("FROZEN_BASELINE_REQUIRED")
    if baseline is not None:
        if len(baseline)!=COHORT or set(baseline)!={r["source_id"] for r in records}:
            raise ValueError("FROZEN_BASELINE_ID_DRIFT")
        for rec in records:
            expected=baseline.get(rec["source_id"])
            if (not isinstance(expected,dict) or
                expected.get("source")!=rec["source"] or
                expected.get("source_sha256")!=rec.get("source_sha256")):
                raise ValueError("FROZEN_BASELINE_CONTENT_DRIFT")
    actual=Counter(r["source"] for r in records)
    if dict(actual)!=expected_counts:raise ValueError("SEVEN_SOURCE_CENSUS_DRIFT")
    statuses=Counter()
    for row in records:
        st=row["status"];statuses[st]+=1
        if st=="SILVER_READY" and not (
            row.get("g5_durable_readback") is True
            and isinstance(row.get("g5_certificate_sha256"),str)
            and HEX.fullmatch(row["g5_certificate_sha256"])
            and isinstance(row.get("g5_certificate"),dict)
            and row["g5_certificate"].get("source_id")==row["source_id"]
            and row["g5_certificate"].get("source")==row["source"]
            and row["g5_certificate"].get("source_sha256")==row.get("source_sha256")
            and row["g5_certificate"].get("status")=="SILVER_READY"
            and digest(row["g5_certificate"])==row["g5_certificate_sha256"]):
            raise ValueError("UNSIGNED_READY_PROMOTION")
        if st not in {"SILVER_READY","HOLD","EXCLUDED","NOT_APPLICABLE","PENDING","RETRY"}:
            raise ValueError("BAD_RECORD_STATUS")
    return {"cohort":COHORT,"sources":dict(actual),"statuses":dict(statuses),
            "all_terminal":not (statuses["PENDING"] or statuses["RETRY"]),
            "silver_ready":statuses["SILVER_READY"]}

def handover_decision(*, old_runs_active, cron_disabled, redispatch_disabled,
                      old_master_snapshot, old_checkpoint_snapshot, exclusive_writer_fence):
    """Safety gate: old runs must STOP before a new production Master writer starts."""
    flags={"old_runs_inactive":old_runs_active==0,"cron_disabled":cron_disabled is True,
           "redispatch_disabled":redispatch_disabled is True,
           "old_master_snapshot":old_master_snapshot is True,
           "old_checkpoint_snapshot":old_checkpoint_snapshot is True,
           "exclusive_writer_fence":bool(exclusive_writer_fence)}
    return {"status":"PASS" if all(flags.values()) else "HOLD",
            "checks":flags,"reason":"" if all(flags.values()) else "G0_OLD_WRITER_HANDOVER_INCOMPLETE"}
