# JARVIS v0.97 V3 — G0–G4 End-to-End Logic Audit (2026-11-17)

Scope: frozen 74,750 source IDs, seven source systems; Bronze originals read-only; no Silver/Gold materialization.

## Evidence precedence and release conditions
1. Source ID + source_sha256 + destination_id from the frozen manifest define each source record; seven-source counts must sum to 74,750 without duplicates.
2. G0: historical BRONZE_INTEGRITY_READY is legacy evidence; only verified destination readback SHA is V3 destination-integrity proof.
3. G1: legacy Format V2/V2.1 classifications are reusable after version/SHA checks, but classification does not certify native Dataset/Era.
4. G2: require official source Dataset identity, valid historical effective period, source-native format signature and source-ID lineage. Era name and header aliases alone are not enough.
5. G3: require necessary fields, source-native units, primary key, null and typed row semantics, appropriate full-file validation and officially attested layout for the actual Dataset/Era.
6. G4: only when G0 through G3 are independently verified may release be certified. Candidate, scanned, sampled and SHA-matched are NOT Silver Schema Ready.
7. No-header grouping is merely a discovery bucket. ZIPs may be mixed Dataset containers; every member requires own evidence.
8. Immutable Delta -> source-specific checkpoint -> readback -> unified Master. Never silently overwrite historical receipts or modify Bronze.
9. Incremental reuse: source SHA + parser revision + ordered observed header/ZIP member SHA + contract Registry revision. No unchanged success is reprocessed; revisions selectively invalidate affected records.
10. Independent seven-source lanes, max concurrency controls, non-fail-fast matrix, 15-minute recovery and a separate main workflow; avoid two writers to same source checkpoint.
11. Only report v097_V3_UNIFIED_MASTER_LATEST.json as the user-facing single total. Distinguish scans, verified contracts and Ready; do not add their overlapping counts.
12. Silver and Gold output counts remain exactly zero until explicit further user authorization.

## Confirmed bugs fixed in repository
- G2/G3 discovery shadowed the newly recovered header evidence with prior V3 data. Corrected; exact source SHA negative tests added.
- Historical HTML row parser risked treating ordinary data rows as table headers. Now only TH or at least two distinct source-contract aliases produce a header candidate.
- HTML parser tuple and non-ASCII bytes test fixtures caused safety failures. Both fixed and rerun in GitHub Actions.
- G3 typed sample evidence originally keyed reuse only by original SHA. Now includes parser revision and native header/contract evidence fingerprint.
- Contract grouping formerly hashed only matched canonical aliases; now hashes full ordered native observed header and labels no-header mega-groups explicitly not certifiable.
- Unified Master reports separate header recovery and G3 typed-sample metrics; all candidate and sampled results remain uncertified.

## Remaining blockers — never mark as complete without evidence
- Registry candidates do not cover every actual dataset/era across all seven sources.
- For each source/dataset/era, official format provenance and source effective-time evidence must be documented, beyond a source-wide link.
- XLSX, XBRL/iXBRL, PDFs, TDCC historical identities, CSV date and complete row validators require dataset-specific contracts.
- Full-file typed consistency, unique keys, native units, semantic date validation, PIT and revisions are not established by 40-row CSV/JSON samples.
- Historical TDCC ZIP aggregate numerical mismatches remain HOLD even where CRC/SHA passed.
- GitHub cron schedule may be delayed; never treat schedule frequency as actual successful execution guarantee.

## Repeatable safety checks
python -m py_compile scripts/v097_g2g3_native_headers.py scripts/v097_g2g3_contract_discovery.py scripts/v097_g2g3_typed_contract_audit.py scripts/v097_v3_unified_master.py
PYTHONPATH=. python scripts/v097_g2g3_native_headers.py selftest
PYTHONPATH=. python scripts/v097_g2g3_contract_discovery.py selftest
PYTHONPATH=. python scripts/v097_g2g3_typed_contract_audit.py selftest
PYTHONPATH=. python scripts/v097_v3_unified_master.py selftest

## Source-native public references
TWSE: https://openapi.twse.com.tw/
TPEx: https://www.tpex.org.tw/openapi/
MOPS: https://mops.twse.com.tw/
TDCC: https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
TAIFEX: https://www.taifex.com.tw/
NDC: https://www.ndc.gov.tw/
FinMind: https://finmindtrade.com/
Public source-wide links are discovery evidence only; they do NOT certify a historical Dataset/Era contract.

## Real source proof and 11/14–11/17 historical-format correction
- 2026-11-17 actual raw TDCC Drive HTML file ID 1--oAGav1QBgijxyNgkM3NVR5JiJ5oAgC, name distribution_20251128_4609_*.html, was independently read in GitHub Run 44117824116 (QA receipt Drive ID 1l8x470kSiq8y5ooumtkOOzYxG4vUgXD_).
- HTML page body carries code 4609 and date ROC 114/11/28; these are **page metadata**, not ordinary table columns. It has **16 physical rows**: distribution tiers 1–15 and total ordinal row 16. Its header uses source-native aliases 股數/單位數 and 占集保庫存數比例 (%). Native SHA/page/field and internally consistent amount/ratio shape were verified, but official PIT and historical security identity remain uncertified, so no G2/G3/G4 release.
- Prior supplementary TDCC JSONL ZIP samples have a distinct **17-row native layout**: tiers 1–15, difference adjustment 16, total row 17. Do NOT impose 17 rows on HTML; nor infer 16-row HTML approval for either ZIP. The historical two ZIPs retain 429 share-count and 20 percent anomalies and production_approved=false.
- TDCC native parser now distinguishes 16-row HTML vs 17-row adjustment archives via **labeled total row**. It validates data date/code against the filename, all native row numeric types, subtotal vs total and ratio sum. File mismatch remains HOLD; it never silently edits bytes.
- 11/16 74,750 original-record census: READY 35,467 and HOLD 39,283 in the **historical Silver input** gate, not V3 G2/G3/G4 Ready. 6,358 migration exceptions were classified, not all repaired. Legacy A/B/C/DEEP/D overlap and must not be added to V3 counts.
- This release also adds bounded complete CSV/JSON/JSONL shape scans (date calendar validity, numeric types, provisional key duplicates), with oversized/unsupported formats explicitly pending. None of these alone certifies historical source edition, source-native unit policy, publication PIT or downstream Silver output.
- Independent source QA historical-reference index: docs.google.com/document/d/1pqunt5SJedVyePk0OFjeHJO90BmUmSuYa2d_-ppJZIg/edit
- Official source links for verification: https://www.tdcc.com.tw/portal/zh/smWeb/qryStock ; https://schema.nat.gov.tw/lists/75 ; https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8 ; https://www.taifex.com.tw/cht/3/dailyFutures
