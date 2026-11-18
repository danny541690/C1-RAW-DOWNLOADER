"""JARVIS R3 pure, read-only gate logic. No Google Drive writes or conversions."""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Mapping, Sequence
import json

GATES = ("G1", "G2", "G3", "G4", "G5")
SOURCES = ("TWSE", "TPEx", "MOPS", "TDCC", "TAIFEX", "NDC", "FinMind")
TERMINAL = {"SILVER_READY", "EXCLUDED", "NOT_APPLICABLE", "HOLD"}
NON_TERMINAL = {"PENDING", "RUNNING", "RETRY"}
COHORT = 74750

def digest(value) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(blob).hexdigest()

def evidence_key(record_id: str, content_sha256: str, gate: str,
                 rule_version: str, *, template_version: str = "",
                 parser_version: str = "", dependency_digest: str = "") -> str:
    if gate not in GATES or len(content_sha256) != 64:
        raise ValueError("Invalid gate or content SHA")
    return digest([record_id, content_sha256.lower(), gate, rule_version,
                   template_version if gate != "G1" else "",
                   parser_version if gate in ("G3", "G4", "G5") else "",
                   dependency_digest if gate != "G1" else ""])

def check_migration(*, source_sha: str | None, destination_sha: str | None,
                    direct_download_sha: str | None = None) -> dict:
    """A path's byte integrity is independent of official historical provenance."""
    reference = source_sha or direct_download_sha
    if not reference or not destination_sha:
        return {"status": "HOLD", "reason": "MISSING_SOURCE_OR_DEST_SHA"}
    if len(reference) != 64 or len(destination_sha) != 64:
        return {"status": "HOLD", "reason": "INVALID_SHA"}
    if reference.lower() != destination_sha.lower():
        return {"status": "HOLD", "reason": "BYTE_MISMATCH"}
    return {"status": "PASS", "reason": "MATCHED_SHA256",
            "provenance": "SEPARATELY_ATTESTED"}

@dataclass(frozen=True)
class Template:
    source: str
    dataset: str
    template_id: str
    start_date: str
    end_date: str | None
    required_fields: frozenset[str]
    optional_fields: frozenset[str] = frozenset()
    aliases: Mapping[str, str] = field(default_factory=dict)
    official_evidence: str = ""
    evidence_verified: bool = False

def template_for(templates: Sequence[Template], source: str,
                 dataset: str, asof: str) -> Template | None:
    matched = [t for t in templates if t.source == source and t.dataset == dataset
               and t.start_date <= asof and (t.end_date is None or asof <= t.end_date)]
    if len(matched) > 1:
        raise ValueError("Overlapping template eras")
    return matched[0] if matched else None

def match_fields(template: Template, observed: Sequence[str]) -> dict:
    """Fuzzy discovery only: all mandatory semantics must be verified."""
    mapped = {template.aliases.get(x, x) for x in observed}
    missing = sorted(template.required_fields - mapped)
    unknown = sorted(mapped - template.required_fields - template.optional_fields)
    if missing:
        return {"status": "HOLD", "reason": "REQUIRED_FIELDS_MISSING", "missing": missing, "unknown": unknown}
    if not template.evidence_verified or not template.official_evidence:
        return {"status": "HOLD", "reason": "OFFICIAL_TEMPLATE_EVIDENCE_PENDING", "missing": [], "unknown": unknown}
    if unknown:
        return {"status": "HOLD", "reason": "UNRECOGNIZED_FIELDS_REQUIRE_REVIEW", "missing": [], "unknown": unknown}
    return {"status": "PASS", "reason": "HISTORICAL_TEMPLATE_VERIFIED", "missing": [], "unknown": []}

def reusable(old: Mapping, expected_key: str, dependencies_valid: bool = True) -> bool:
    return (old.get("evidence_key") == expected_key
            and old.get("status") in ("PASS", "REUSED_PASS")
            and old.get("durably_committed") is True
            and dependencies_valid)

def next_gate(results: Mapping[str, str]) -> str | None:
    for gate in GATES:
        state = results.get(gate)
        if state not in ("PASS", "REUSED_PASS", "NOT_APPLICABLE"):
            return gate if state is None or state in ("PENDING", "RETRY") else None
    return None

def disposition(results: Mapping[str, str], *, in_scope: bool = True,
                excluded: bool = False, durable_release: bool = False) -> str:
    if excluded:
        return "EXCLUDED"
    if not in_scope:
        return "NOT_APPLICABLE"
    if any(v == "HOLD" for v in results.values()):
        return "HOLD"
    if all(results.get(g) in ("PASS", "REUSED_PASS", "NOT_APPLICABLE") for g in GATES):
        return "SILVER_READY" if durable_release else "PENDING"
    return "PENDING"

def reconcile(states: Sequence[Mapping]) -> dict:
    keys = [x["record_id"] for x in states]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate record_id")
    totals = {s: 0 for s in (*TERMINAL, *NON_TERMINAL)}
    sources = {s: 0 for s in SOURCES}
    for item in states:
        state, src = item["status"], item["source"]
        if state not in totals or src not in sources:
            raise ValueError("Unknown state or source")
        totals[state] += 1
        sources[src] += 1
    if sum(totals.values()) != len(states):
        raise AssertionError("Cohort mismatch")
    return {"count": len(states), "states": totals, "sources": sources,
            "complete": len(states) == COHORT and not any(totals[s] for s in NON_TERMINAL)}
