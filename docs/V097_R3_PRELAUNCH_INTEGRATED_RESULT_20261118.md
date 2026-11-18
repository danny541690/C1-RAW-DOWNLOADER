# JARVIS v0.97 R3 | Integrated prelaunch evidence | 2026-11-18

## Implemented in isolated staging

- PR #61, branch `r3-bronze-silver-ready-staging-20261118`.
- Single GitHub Actions prelaunch workflow `.github/workflows/v097_r3_one_click_prelaunch.yml`.
- Completed combined Run **44233821858**: gates-and-synthetic SUCCESS; real-bronze-read SUCCESS; real-70-sample SUCCESS; drive-staging-readback SUCCESS; final SUCCESS.
- Real 70: TWSE 10, TPEx 10, MOPS 10, TDCC 10, TAIFEX 10, NDC 10, FinMind 10. **70/70 0.97 destination SHA matched** existing frozen manifest SHA; 0 errors, 0 mismatches, no candidate skipped. Seven cohorts sum to 74,750. These are stratified samples, not all 74,750 originals.
- All 70 selected files returned `SCHEMA_PROFILED_NEEDS_MAPPING` in existing candidate parser. This is not an approved G2/G3 historical dataset contract or Silver input mapping.
- Live Google Drive staging receipt create/readback SUCCESS; isolated folder `03_DATA_QUALITY/R3_STAGING_PREFLIGHT_ISOLATED`; receipt `r3_prelaunch_write_readback_run_44233821858.json`; log confirms `certificates_released=0`, `production_writes=0`.
- GitHub snapshots R1/V3 prior runs and frozen cohort arithmetic checked; old workflows still dispatch.
- Historical source-format period selftest and gate semantic/negative/duplicate/retry/replay/full-cohort synthetic tests passed.

## Explicit production blockers (not claimed complete)

1. **G0 handover:** retire or disable every old R1/V3/G2G3 producer AFTER immutable last-Run/Checkpoint snapshot and verify no in-flight/queued legacy process remains; 17 non-frozen legacy workflows were identified, 8 cron schedules. Distinct workflow concurrency groups are NOT a shared transaction lock. Existing live R1/V3 may still be writing.
2. **G1 full-chain migration:** the tested SHA is only frozen source_sha256 versus 0.97 destination. 0.93 source identity/history and official->0.93 lineage are not independently verified by this test. Import durable 0.93 migration receipts and handle direct official->0.97 paths; flag missing provenance separately.
3. **G2 real official dataset eras:** current historical source period registry is informational, not an official per-dataset field-level attested contract with appropriate aliases and effective dates. Candidate similarity is never automatic PASS.
4. **G3 real minimum parsing:** 70 files are structurally profiled as candidate; full required-field identity/semantic checks with approved official evidence are pending.
5. **G4 mapping:** real Silver input columns, unit/date/identity mapping and historical security scope must be evidenced per dataset; no physical Silver conversion.
6. **G5 durable formal ledger:** staging receipt tests Google Drive persistence but DOES NOT prove production exclusive Master, transactional lease / CAS, durable per-record G1–G5 certificates, replay invariants and signed final Silver Ready.
7. **Full live integration:** 700-worker concurrent Drive simulations, actual 1,000-file cutover and halted-run restart + replay still require environment-backed tests. Synthetic 700/1,000 cases do not count.
8. **Production all-record reconciliation:** 74,750-record frozen manifest was counted, but no R3 per-file processing or terminal reconciliation has been executed. Formal R3 Ready count remains UNISSUED.

## Safeguards

- No original Bronze mutations; no Silver or Gold.
- No R3 production Master or READY certificate was issued.
- PR remains Draft and must not be merged until the above blockers are satisfied and the full G0 safety handover is proven.
- Staging CI green means **prelaunch tests successful, production release blocked**.
