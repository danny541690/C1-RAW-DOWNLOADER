# JARVIS v0.97 — Seven-source format validation standard V2 (2026-11-19)

**Status:** mandatory fail-closed *Silver Ready* policy; not Silver/Gold transformation.
**Executable policy:** `scripts/v097_seven_source_release_standard_v2.py`.
**Master validator:** `scripts/v097_acceptance_engine_r1.py`.
**Standard ID:** `JARVIS_V097_SEVEN_SOURCE_FORMAT_G0_G5_V2_20261119`.
**Frozen seven-source population:** 74,750 original Bronze files.

## Authoritative hierarchy and the two-track trap
1. R1 Master `v097_R1_ACCEPTANCE_MASTER_LATEST.json` / immutable run report is the **only formal G0–G4 and Silver Ready population count**.
2. R3 `r3_g2_seven_source_325_official_qa_master_run_44285197374.json` contains **325 source-vintage QA matches, not R1 certificates**. They are candidate evidence, never an automatic R1 promotion.
3. Per-file R1 G2/G3 certificates must bind immutable `source_id`, `source_sha256`, source, Dataset, historical edition, official comparison evidence and contract revision.
4. Run Success, official page HTML 200, a SHA self-test, or G1 header alias candidate are never formal G2 PASS.
5. The dashboard Excel is a **versioned reporting snapshot**, not the live authority; machine release derives from this module + R1 Master and Checkpoints.

## Scope and baseline
| Source | Frozen Bronze | R3 source-vintage QA | R1 G2 PASS on R1 run 44341752915 |
|---|---:|---:|---:|
| TWSE | 12071 | 1 | 0 |
| TPEx | 13200 | 1 | 0 |
| MOPS | 1935 | 1 | 0 |
| TDCC | 40384 | 0 | 2 |
| TAIFEX | 3140 | 0 | 1 |
| NDC | 320 | 320 | 0 |
| FinMind | 3700 | 2 | 0 |
| **Total** | **74750** | **325** | **3** |

As of R1 run **44348224015** after the V2 deployment, the same 3 G2 passes remain, G3 passes = 0, G4 Ready = 0, and Silver/Gold generated = 0.

## Mandatory test-to-release chain
- **G0 immutable Bronze:** correct source_id and destination_id, actual readback SHA256, ZIP member CRC/SHA when applicable, filename/lineage and original bytes protected from writes. Source unavailable != damaged original.
- **G1 original native format:** exact source + Dataset + file/member type + effective historical layout, required original field semantics; aliases/column order/optional columns may vary if verified. Fuzzy matching never issues certification. Recognize legacy GAAP/IFRS, A05, distinct TAIFEX datasets, 2007 TPEx transitions, NDC methodology changes, and TDCC tier editions.
- **G2 same-date official content:** obtain proper first-party issuer Dataset for matching date, stock/contract identity, header and every effective native row/column; normalize only documented representation (thousands commas, whitespace, TDCC final tier ordinal mapping). Official response SHA computed internally, never insist issuer publishes digest or own G2 certificate. Missing historic official data => evidence HOLD, not corruption. Per-file `R1_G2_DATASET_CERT_V2` with immutable source SHA and readback.
- **G3 minimal typed parsing:** all native data rows, expected row count and primary key, numeric types and units, NULL/ellipsis, revisions, duplicated rows, and same Dataset binding to G2. `seven_source_standard_version` MUST equal this V2 identifier in the formal G3 certificate. G3 does not generate Silver.
- **G4 Silver Ready:** G0–G3 all PASS, complete lineage, correct stock scope (listed/OTC), dataset period and defensible data-availability/PIT rules. Observation date does NOT by itself establish intraday availability. No Silver or Gold materialization. Files outside stock scope can be EXCLUDED but are not READY.
- **G5 unified reconciliation:** all 74,750 immutable source IDs accounted, no orphan/duplicate, exact per-source counts, checkpoint SHA consistency, recorded rule version for any READY file, no uncertified READY; preserve errors/RunID/lineage. Never promote a source's aggregate sample approval to every file.

## Data-availability / PIT
Historical observation date identifies the record's period, **not** necessarily the earliest time available to a backtest. G2 data integrity and G4 trading availability are separate checks. Conservative next-day availability is appropriate when actual publication timing is unknown. An official 2026 snapshot of a 2001 observation does not prove its value was known in 2001.

## Proven seven-source recipes (do not extrapolate)
- TWSE R3 one original MI_MARGN margin record, run 44268565232; mixed ZIP children require independent Dataset identity.
- TPEx R3 one 2024-06-20 valuation record, run 44267841704; valuation is not OHLCV.
- MOPS R3 one 2025-02 monthly-revenue source-vintage, run 44285197374; 857 company values, exclude 2026 later IPO codes and avoid name backfills.
- TDCC R1 two 2026-10-08 HTML tier files, run 44341433741; CSRF token and `method=submit`, `firDate/scaDate/sqlMethod/stockNo`, www.tdcc portal; 15 bands + total are 16 HTML rows, archive's 17th ordinal is total.
- TAIFEX R1 one January 2024 LARGE_TRADER original CSV, run 44337508464; 22 days x 1150 = 25300 effective rows; official requests chunked by 3 trade dates; exclude notes with auditable explanation.
- NDC R3 320 files from the October 2026 official workbook snapshot, run 44260700121; preserve literal missing values, never infer contemporaneous PIT.
- FinMind R3 two original provider source-vintage samples, run 44285197374; dataset ID, parameters, revisions, scope and row units matter.

## Priority error taxonomy
DOWNLOAD_SOURCE / BYTE_INTEGRITY / DATE_IDENTITY / HEADER_SCHEMA / CONTENT_VALUES / METADATA_SCOPE / PROOF_REGISTRY / SCHEDULER. In particular:
- 404/520/timeouts/auth are fetch errors; do not label Bronze corrupt.
- Existing R3 overlay and R1 Master must NEVER be added together.
- TDCC old Ajax and upper-case StockNo/REQ_OPR failed; submit using current portal state.
- TDCC 16/17 tier mismatch is a known terminal-row presentation difference, not a numeric mismatch.
- TAIFEX LARGE_TRADER is not FUTURES_DAILY; 3-day official blocks and checkpoint are required to avoid HTTP 520.
- NDC literal missing cells remain missing; no zero imputation.
- FinMind API response version and third-party provider data differ from original government data.
- MOPS GAAP vs IFRS/XBRL vs iXBRL must be dataset- and period-specific.
- G3 schema certificates cannot be inferred from G1 candidates.
- Recover errors up to three retries; preserve a full error ledger and continue unrelated valid files.

## Rules for all subsequent runs
1. Fetch baseline manifests and latest R1 Master, R3 overlay and error ledger.
2. Validate approved source / Dataset / native era profile first; sample only novel format once.
3. Reuse unchanged SHA- and version-matching formal certificates; process new/HOLD incrementally.
4. Before a file gets G4 READY, run the machine `may_release` V2 check against both formal G2 and G3 certificates and all gates.
5. R1 aggregate must fail-close if any READY checkpoint lacks the V2 identifier or a PASS chain.
6. Persist immutable per-run report, latest Checkpoint and Master, evidence locations and error classification to Drive.
7. Keep Bronze bytes unchanged and **never** invoke Silver/Gold transform workflows.
8. Every future dashboard refresh includes the exact immutable R1 run, QA overlay run and V2 version; do not display it as a live dashboard if not automatically refreshed.

## Source pointers
- R3 QA: https://drive.google.com/file/d/1zi603mMo-6GQQOrZxArvjdvzQfqYdfp8/view
- Historical SOP: https://drive.google.com/file/d/1HF3bQ_6B6hvQUGm9VR_ZqlI3E4nR55KB/view
- R1 baseline Master: https://drive.google.com/file/d/1QlkkzMHJEdVntQhd1rBys72WAg4ScVxV/view
- R1 V2 Master: https://drive.google.com/file/d/1F-Rah2RZHKToAD9uNbf-FJFUm6AF1zHu/view
- TDCC G2 cert: https://drive.google.com/file/d/18YW_Kvr_Lx8Db4-TcsWO56Dn801LY8u1/view
- TAIFEX G2 cert: https://drive.google.com/file/d/1DcoMJW9uv7JyEorXPzGptCYBgdp1CEt6/view

**Change control:** Future modifications to standard must bump standard version, add explicit regression tests, and retain previous reports; no silent backfill of a newer standard into older certificates.
