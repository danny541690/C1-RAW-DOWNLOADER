# JARVIS v0.97 R3 — G0 handover and production release checklist

Status: STAGING ONLY. This branch is not authorized to release a production Silver Ready certificate.

## Frozen cohort and previous provenance

- Historical frozen target: 74,750 logical records.
- R1 checkpoint observed: evaluated 41,140, not evaluated 33,610; all old G2/G3 pending. R1 run 44222329899; the checked fraction is not Silver Ready.
- V3 checkpoint observed: checked 40,240; not checked 34,510; schema_ready_certified 0, silver_materialized 0, gold_materialized 0.
- Preserve old evidence and classify by source file ID, destination ID, content SHA, dataset, as-of date, run, contract version.
- Old historical READY/HOLD must not be promoted as R3 READY without validating relevant evidence.

## Identified running workflows and collision

- R1 acceptance: .github/workflows/v097_acceptance_r1.yml includes 15-minute cron (9,24,39,54) and automatic workflow_dispatch continuation.
- V3 acceptance: .github/workflows/v097_v3_acceptance.yml includes automatic workflow_dispatch continuation.
- G2/G3 resume: .github/workflows/jarvis-v097-g2g3-resume.yml includes 15-minute cron (7,22,37,52).
- 466 workflow files found, 449 shared the no-op GLOBAL FREEZE file blob, 17 had distinct content.
- R1 and V3 both use their own independent concurrency groups and can write their respective Drive masters while R3 would run: absence of cross-workflow global locking is a collision risk.
- Required: discover all active scheduled, workflow_dispatch, push and programmatic entrypoints, and all in-flight runs; record immutable handover snapshots; disable old dispatch and await/terminate old writers safely; verify no late writer can publish.
- DO NOT merge staging into main or unfreeze legacy workflows until that is complete.
- Existing repository is PUBLIC: do not commit user-specific Drive IDs, secrets, proprietary strategies or personal information.

## R3 contract

G0: inventory, freeze cohort, historical artifact import, source-specific task queue, one release writer, abort-on-unauthorized-collision.
G1: official->v0.93->v0.97 or official->v0.97 observed paths. Distinguish byte integrity vs source provenance. SHA mismatch HOLD, never fuzzy.
G2: official-era template registry per source/dataset/effective period. Fuzzy discovery may suggest template; missing critical semantic fields HOLD pending official proof. A score such as 8/10 is not a pass credential.
G3: minimal structural parsing only (no numeric full-market backtest).
G4: required Silver input mapping, provenance, date/units/identity. No materialization.
G5: certificate DAG, exact-row and source counts, immutable append-only evidence, durable Drive readback, release after all preceding passes.
FinMind treated as seventh supplementary source distinct from six official sources.

## Gate certificate fields

record_id, content_sha256, source_id, dataset_id, effective_date,
gate_id, rule_version, template_version (where relevant), parser_version (where relevant),
dependency_evidence_digest, source_file_id, destination_file_id, run_id,
status, reason, created_at, durable_commit_reference.

Only a valid signed-off durable certificate with matching dependencies can be reused.
Template/contract updates invalidate only impacted gate certificates and descendants.

## Seven isolated source workers

Source-local queue, checkpoint, idempotency key and lease with compare-and-swap;
one central committer; per-source fail isolation and retry <=3 for transient errors.
No worker may directly release READY or modify original Bronze.
On Google authorization errors, no fabricated release certificate.
Use 15-minute watchdog only for missed continuation, not as batch delay.
Stop only after every record has a terminal status and immutable final report reconciles to 74,750; HOLD is closure, not READY.

## Three bundled release tests

1. 70 case functional suite, seven sources including historical alias, missing core field, official-era invalidity, direct download, ZIP SHA.
2. 700 case multi-worker simulation with lease races, worker death, OAuth failure, duplicate dispatch and retry.
3. 1,000 case handover/continuation simulation with frozen legacy, release durability readback and interrupted master.
The current Python staging tests are SYNTHETIC ONLY. They are foundational unit checks, NOT those complete live Drive/GitHub integration tests. Do not claim pass of the above from staging unit CI.

## Do not release until

- Full enumeration and classification of 17 non-frozen workflows, active runs and mutating scripts
- Real Drive-backed 74,750 row baseline fully read and reconciled
- Official era registry and dataset availability starts verified
- Durable per-source queue, leases, checkpoints and release writer implemented and reviewed
- All three actual bundled integration suites complete with evidence
- Historical migration SHA evidence imported and invalid ones isolated
- Credentials validated and report written/read back in a NEW R3 namespace
- No Silver/Gold code path reachable
