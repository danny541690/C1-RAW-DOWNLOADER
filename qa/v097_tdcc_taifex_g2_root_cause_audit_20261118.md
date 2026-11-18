# JARVIS v0.97｜TDCC/TAIFEX G2 Root Cause Audit｜2026-11-18

## Evidence layers
- Frozen cohort: 74,750; TDCC 40,384; TAIFEX 3,140.
- R3 immutable source-vintage QA: 325 G2 source-vintage proofs globally (NDC 320, TWSE 1, TPEx 1, MOPS 1, FinMind 2). TDCC and TAIFEX: no formal source-vintage G2 PASS yet.
- TDCC R3 native 10/10 SHA and 15-tier-plus-total layout PASS. Official 2026-11-13 snapshot is **not** evidence for 2026-10-08 values.
- TAIFEX 2024-01 raw original: 25,304 rows including native notes, CP950; historic issuer POST had ConnectionError.
- This report is not a live GitHub Actions Run result. Workflow actual status must be checked in Actions UI by run number and/or uploaded artifacts.

## Verified engineering problems and applied changes
1. Prior GitHub connector workflow-run lookup filters PR-associated runs. It cannot establish whether push/scheduled runs happened; do not treat an empty result as 'not run'.
2. Multiple overlapping TDCC/TAIFEX cron jobs were configured. Removed cron from old pilot and native-date workflows; retained manual dispatch. Kept hourly canonical `.github/workflows/v097_exact_date_g2_backcheck.yml` at minute 13 UTC.
3. Previous canonical workflow depended entirely on Google Drive writes to see results. Canonical workflow now writes `GITHUB_STEP_SUMMARY` and uploads per-source `selftest` and `compare` logs even on failed steps. Diagnostics can be retrieved when OAuth fails.
4. Prior HTTP 200 response handling could decode an HTML anti-bot/error page as CSV and produce false data differences. The parser now explicitly classifies HTML_NOT_CSV, no matched official data rows, and source exceptions separately.
5. Earlier TDCC audit conflated native 16-row HTML and official 17-row adjustment/total format. The mapping 1..15, HTML total 16 -> official total 17 is only a format conversion; numeric comparison requires same weekly date, same security.
6. R3 official current API 2026-11-13 for code 2365 cannot certify Bronze week 2026-10-08. Same-week third-party archive is separate provenance class and cannot mint first-party origin or PIT proof.
7. TAIFEX historical large-trader dataset is NOT daily futures quotes. Exact dataset ID and 2024-01-02..04 dates must match, with footnotes excluded from transaction rows. Official HTTP POST failure must be SOURCE_FETCH_HOLD rather than BRONZE_CORRUPTION.
8. Previous proof scripts deliberately hardcode new formal G2 pass=0. This means successful numeric candidate matches will not automatically create an R1/R3 formal per-file G2 certificate. Issuance needs separate official provenance, date, dataset, SHA, independent review and authoritative evidence.
9. Historical formats cannot be certified by filename and era alone; filename date is parser-candidate routing only, not source publication proof.

## Correct execution and readout
- Main workflow: `https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/workflows/v097_exact_date_g2_backcheck.yml`
- Only one canonical periodic source-diff job. Old pilots manually available.
- Verify Actions Run ID + matrix job statuses (TDCC and TAIFEX separately); inspect artifacts `v097-g2-TDCC-diagnostics-<run_id>` and `v097-g2-TAIFEX-diagnostics-<run_id>`.
- If `selftest` failed: fix code/dependency. If `compare` failed: identify OAuth/Drive access/remote source exception. If comparison finishes HOLD: inspect source date availability/dataset/field-level evidence. A successful job != formal G2 pass.
- Only after matched first-party original source evidence and independent QA certificate may formal G2 pass be incremented; leave G5/Silver/Gold unchanged.
- Checkpoint reuse: preserve each exact source_id, destination SHA, template+rule version. Do not re-download or modify Bronze to cure source endpoint problems.
