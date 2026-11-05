# C1 v0.95 phase-1 governance baseline (2026-11-05)
STATUS: SCHEMA_DEFINED_NOT_POPULATED
BULK_COPY_APPROVED=false
RELEASE_APPROVED=false
Source families: TWSE, TPEx, MOPS, TDCC, TAIFEX, NDC, FinMind.
Physical Bronze classes: TWSE, TPEx, MOPS, TDCC, TAIFEX, NDC, FinMind_Free, FinMind_Backer.
FinMind unknown tier -> quarantine. Official data first; FinMind only verified gap fill. TSE/OTC analysis only; emerging stocks preserved without analytical release.

Required durable ledgers:
- SOURCE_REGISTRY: source_class_id, source_family, tier, license, market_scope, endpoint, availability_evidence, status.
- DATASET_CONTRACTS: dataset_id, source_class_id, raw_format, input/output schema, units, primary_keys, published_at, revision, PIT, Git SHA.
- TASK_LEDGER: task_id, mode(migration/backfill/daily/Backer), source, dataset, period, state, retries, checkpoint, github_run_id, error.
- MANIFEST_INDEX: source_file_id, destination_file_id, drive_parent_id, SHA256, native bytes, version, dataset, period, status.
- CHECKPOINTS: task_id, cursor, last_committed_artifact, readback_hash, lease_owner, fencing_token.
- ISSUE_REPAIR_HISTORY: classified reason, owner, retries, resolution, before/after hashes, evidence.
- RUN_LOGS: workflow, SHA, Run ID, period, API calls, result, Drive receipt.
- DATA_QUALITY_STATES: EXPECTED, FETCHED, VALIDATED, PIT_APPROVED, GOLD_APPROVED independently.

Exact flow: legacy read-only inventory -> dataset contract -> staging SHA copy -> native Bronze -> typed Silver and row reconciliation -> PIT -> real Gold -> Drive readback SHA -> backup restore -> incremental catch-up. No manifest-only success. No GitHub Actions success treated as Drive publication. 1 publisher per partition until CAS+fencing two-runner tests pass. Persist checkpoint only after verified commit. Retry transient errors up to 3; no re-download of matching accepted SHA; quarantine structural/PIT unknown and continue unrelated tasks. Negative tests: unknown FinMind tier, missing historic security master, receipt byte mismatch, missing ACK, CAS conflict, MOPS manifest-only, rate 429. Seven-source actual E2E small samples required before bulk. Preserve legacy v0.93.

Outstanding evidenced blockers: TDCC DURABLE_PUSH_REJECTED, release code hash changed, Git/Drive CAS & restore incomplete, TWSE receipt byte mismatch, incomplete PIT and security-master evidence. This is a governance rule specification, not proof that workflows implement it.
