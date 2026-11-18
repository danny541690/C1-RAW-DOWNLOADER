# JARVIS v0.97 R3 | TDCC / TAIFEX 同日原檔格式差異清單
Date: 2026-11-18 (Asia/Taipei)
State: SOURCE_NATIVE_VERIFIED / OFFICIAL_SAME_DATE_PENDING
Formal G2 PASS issued in this report: 0

## TDCC: 3 frozen Bronze original HTML pages inspected directly
| Original date | Security | HTML header | Band rows | Total row | Total holders | Total shares | Tier 1 shares | Tier 1 holders | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-10-08 | 2365 | 序／持股/單位數分級／人數／股數/單位數／占集保庫存數比例 (%) | 15 | 16 合計 | 98,198 | 221,528,496 | 2,405,557 | 58,662 | NATIVE_STRUCTURAL_MATCH |
| 2026-10-08 | 3258 | same | 15 | 16 合計 | 91,865 | 273,367,558 | 17,079,960 | 53,222 | NATIVE_STRUCTURAL_MATCH |
| 2025-11-07 | 2433 | same | 15 | 16 合計 | 8,370 | 144,496,011 | 378,774 | 2,359 | NATIVE_STRUCTURAL_MATCH |

Official current TDCC OpenAPI `https://openapi.tdcc.com.tw/v1/opendata/1-5` uses rows 1-15, adjustment/reserved row 16, total row 17 in the previously captured 2026-11-13 stock-2365 response. This is a **format layout mapping**; do not compare the 2026-10-08 Bronze figures against 2026-11-13 numeric figures. Earlier 2365 official response: total holders=97,871; total shares=221,528,496. Difference in holder count from original 2026-10-08=327; this is a **cross-date variance**, NOT raw corruption.

Difference classes:
- TDCC-01: HTML 16-row total vs OpenAPI 17-row adjustment+total: recognized variants, never reject blindly.
- TDCC-02: exact published week absent in current official API response: ORIGIN_SAME_DATE_HOLD, not data damage.
- TDCC-03: original HTML security/date parsed from BODY and filename, verify both before G2 promotion.
- TDCC-04: special nonordinary securities require effective-date classification; do not infer listed/OTC ordinary stock.
- TDCC-05: archive 429 share-total and 20 ratio discrepancies are independently quarantined from clean HTML cases.

## TAIFEX: Historical 2024-01 source evidence
Frozen record source_id `1V3tY6CRlSB6JjOYld8sFPxmv2vDdg3tu`, sha256 `cb8aec76cd7f1a3b4c410f75b979bcb2149ca5d1e79f5e1c8056d911c8a1ef36`, recorded as 25,304 CSV rows including header/notes, CP950 encoding. Example trade dates selected 2024-01-02, 2024-01-03, 2024-01-04. This row count is **from the earlier persisted R3 QA receipt**, not a newly fetched original in this ledger.

Original 2024-01 captured dates extend 2024-01-02 through 2024-01-31. Native non-date first-column tokens include the footnote on weekly-contract absence versus 0 open interest, the trader group codes 0/1, and month category 666666 / yyyymm / 999999.

- TAIFEX-01: a footnote is not a daily trade-data record. Split header / date-stamped data / native notes.
- TAIFEX-02: trailing empty CSV cells can be tolerated but extra non-empty cells must be mapped.
- TAIFEX-03: LARGE_TRADER_FUT is not FUTURES_DAILY or spread order. Dataset-specific identity required.
- TAIFEX-04: Official historical month/dated POST previously returned ConnectionError; no authoritative byte/content equality proof.
- TAIFEX-05: day-session / after-hours effective trading-date conventions must be kept explicit.

## Rerun and gates
Workflow: `.github/workflows/v097_two_source_native_date_diff.yml`.
- Only exact date/security or exact date/dataset official responses can contribute to formal G2.
- On successful actual action, script writes Drive QA receipts and LATEST pointers per source.
- Does not overwrite Bronze, formal R1 G2 certificate, official G5 Master, Silver or Gold.
- Missing official same-day dataset is a distinct evidence HOLD and should not trigger unnecessary fresh Bronze downloads.

## Reference receipts
- TDCC R3 native 10-file audit run 44283350941.
- TDCC official API matched-week attempt run 44285828754.
- TAIFEX historic original comparison run 44274879527.
- R3 seven-source formal source vintage QA run 44285197374.
