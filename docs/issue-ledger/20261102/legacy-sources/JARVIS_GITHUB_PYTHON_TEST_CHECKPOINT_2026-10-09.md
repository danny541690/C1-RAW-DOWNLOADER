# JARVIS GitHub/Python Test Checkpoint — 2026-10-09

Source conversation: 股票系統C0.91_1. Recorded 2026-10-10.
Status: reconstructed from prior conversation summaries, NOT a fresh verification of all GitHub Actions logs/artifacts. This document preserves continuity and is not itself test evidence.

## Identity and scope
- Repository: danny541690/C1-JARVIS; branch main.
- This checkpoint concerns GitHub Actions, Python, and TWSE historical-data validation. DO NOT confuse it with earlier XQ Raw capability tests.
- Master workbook referenced in discussion: C1_v0.92_JARVIS_MASTER_R5.xlsx (test registry, DQ, evidence manifest, PIT, QA governance). Its actual presence and latest revision have not been reverified here.

## Reported test outcomes
| Test | Reported result | Details |
|---|---|---|
| PY-002 | PASS workflow execution | Run #2, commit f7f961d, twse-api-test success and 1 artifact; this alone did not validate fetched rows/fields/hash |
| PY-005D-R | PASS | 100 stocks; Golden 700/700 |
| PY-006A | PASS | 147/147 |
| PY-006B | PASS_WITH_WARNINGS | 5 warnings |
| PY-006C V2 | PASS_WITH_WARNINGS | Warnings unresolved |
| PY-006D | INCONCLUSIVE | No definitive result |
| PY-006E-C | INCONCLUSIVE | TWSE TWT53U returned 1,365 records dated 2026-10-09; specified 5 stocks found, but requested historical date 2026-10-07 NOT verified; historical_query_verified=false |
| PY-006E-E | PROPOSED / NOT VERIFIED RUN | Cross-source historical date validation |

## Current gates
- QA-006: OPEN / unresolved.
- QA-014: referenced as unresolved in prior discussion; recheck authoritative tracker.
- Production Gate: BLOCKED. No release authorization from these results.

## Next test: PY-006E-E
- Compare TWSE STOCK_DAY_ALL (reported validated 2026-10-07 historical snapshot) with TWT53U queried for 2026-10-07.
- Check as-of date explicitly before comparing: do not pass current-day data as historical.
- Cross-check volume, traded value, transaction count, symbols, units, and missingness; report per-case PASS/FAIL/INCONCLUSIVE and retain response metadata, hashes, and artifacts.
- Do not modify OHLC to make a comparison pass.
- Treat UNAVAILABLE separately from zero.
- If TWT53U does not support a verifiable historical query, keep result INCONCLUSIVE and gate BLOCKED.
- Prefer a consolidated GitHub Python test runner with independent assertions and evidence for each data source.

## Continuation protocol
1. Read this checkpoint and actual GitHub repository workflows/logs/artifacts before stating that a test has newly passed.
2. Reconcile each reported status against the authoritative Evidence Manifest and master workbook.
3. Preserve prior statuses rather than overwriting them without evidence.
4. Record new run ID, commit SHA, tested date, API endpoint, row counts, source timestamp, field-level assertions, warnings, evidence paths, and gate decisions.
5. Update this checkpoint when a new test milestone is verified.

## Historical XQ note (separate scope)
Earlier XQ Raw testing included OHLC historical snapshots and credit/short/SBL balance-closure checks; these are NOT evidence that the GitHub/Python TWSE historical PIT tests passed.

