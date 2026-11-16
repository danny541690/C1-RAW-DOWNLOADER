# JARVIS v0.97 — Seven-source historical parser, three-way evidence and Silver-input gate audit

Audit baseline: 2026-11-16, GitHub run **43812215653**, fixed complete release cohort **74,750**, official input READY **35,467**, HOLD **39,283**. JSON machine-readable exhaustive status census: `v097_SEVEN_SOURCE_COMPLETE_ERROR_CENSUS_43812215653.json` on Google Drive. Counts from different stages ARE NOT ADDITIVE. This inventory is a source-to-Silver *input* QA report; it DOES NOT imply materialized Silver Parquet, 400+ Gold indicators or backtest PIT clearance.

## Immutable acceptance contract

For every record and every required dataset partition: original Drive object + SHA receipt, native parser version and exact historical format, dataset identity, business key, market type as of trade date, row schema + null policy, numeric unit/scale/sign, source-specific effective date and publication/revision time, second independent official or provider same-key numerical evidence, full-row and full-column coverage with discrepancy log, both-way file-to-field lineage, and independent release signed by stage D. A sample, provider URL in a manifest, identical self-retrieval, or landing-page SHA is NOT independently verified historical numerical data. Preserve 3-attempt stop/exception, never zero-fill, never quietly forward-fill, and exclude emerging/non-ordinary securities from ordinary TWSE/TPEx equity output.

## TWSE — historical formats and actual failures
- Original A: 11,545 ZIP content awaiting proof, 508 parsed awaiting origin/PIT, 18 dataset identity.
- C: 7,240 manifest+numeric awaiting official, 2,406 unresolved dataset, 13 bad linkage, 10 absent proof. D: 1,437 numerical independence HOLD; 3 sample-only witnesses; 242 previously READY preserved.
- Independent close witness: 11 matched sampled close prices, 18 no matching single-day equity quote, 3 retry/error in the inspected checkpoint. Not full ZIP certification.
- Official A05 e-shop historical daily price product begins 2003-12-01, 14:00/15:30/17:30 deliveries have different inclusion of odd lots/block trades/after hours; A05+ index 2019-04-30; documented A05 revisions 2021-04-12, 2021-06-28, 2022-01-24, 2023-01-16, 2024-05-27 and 2025-04-28. Public daily closing query begins 2004-02-11: NOT proof that daily price did not exist in earlier data products.
- Repair: separate STOCK_DAILY_OHLCV vs INDEX vs VALUATION vs MARGIN vs INSTITUTIONAL vs LENDING vs FOREIGN_HOLDING; categorical 成交統計 is never numeric. Require per-member SHA + exact publication/trading-date/stock/metric match; do not compare adjusted and unadjusted prices.
- Official: https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8 and https://www.twse.com.tw/zh/trading/historical/mi-index.html

## TPEx — historical formats and actual failures
- Original A: 11,171 ZIP, 963 unknown JSON, 491 period conflict, 291 parsed pending origin/PIT, 252 unknown extensions, 32 table content errors.
- C: 9,266 numeric/manifest waiting official, 654 unresolved dataset, 104 absent manifest, 14 manifest conflict, 1 numerical/width conflict. D: 1,537 lacking independent numbers, 10 sample-only, 229 previously READY.
- Official historical equity quotes: 2003-08–2006-12 archived view; 2007-01-02–04-20 separate link; separate 'excluding fixed-price' view 2007-01–06; modern views thereafter. Never assume same daily pricing scope / market-cap quote as stock OHLCV. Modern OpenAPI snapshot is not a historical date argument.
- Repair: first distinguish market capitalization rankings from OHLCV; build historical schema keyed by dataset+source delivery and effective period; convert ROC dates separately from contract/pricing dates; use the live successful historical official tradingStock JSON for dated price when applicable, and compare unadjusted FinMind stock/day.
- Official: https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html and https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html

## MOPS — historical formats and actual failures
- A: 1,770 ZIP archive member still needs full financial receipt, 117 unknown JSON, 48 HTML matrix parsed but filing/PIT pending. D: 1,779 without independent numeric proof, 115 native semantic HOLD, 0 formal READY.
- Must not label every raw .raw financial member as unidentified purely due extension. Identify binary magic, HTML matrix, text fixed-width, XML/XBRL, iXBRL facts, TXT finance format, versions GAAP/IFRS, XBRL taxonomies and fiscal reporting deadlines.
- Explicit MOPS/TWSE old TXT financial example: report kind (3 bytes), 6-byte company, 5-byte year/quarter, 6-byte account ID, signed fixed-width numbers; example documentation denotes thousand-NTD and EPS requires separate scale. Do not multiply EPS with monetary billion conversion. Annualized and standalone quarterly financial facts are NOT interchangeable. For each numeric value preserve accounting concept, entity, period, context, unit, release timestamp, amendment/correction version.
- Repair: ZIP raw member MIME probing; official financial filing raw historical same-company same-period same-concept numerical check; FinMind `TaiwanStockFinancialStatements` secondary comparison on equivalent period+concept; PIT timestamp from original filing archive, not current download time.
- Official format: https://www.twse.com.tw/staticFiles/listed/manual/ff80808164d4e32d0164d96e1081001b.pdf

## TDCC — historical formats and actual failures
- A: 33,693 HTML code-consistent source-accepted; 5,387 historical security class/origin pending; 1,006 distribution-table QA; 289 date evidence; 5 unknown JSON and 4 ZIP. 6,691 formal HOLD.
- Official weekly holdings reflect last business day, owner-ID aggregation, tier holders/shares and percentage denominator; historical archive begins July 2008 and query service retains one year. Do not substitute today's share master for historical ID/security type; Y-codes, ETF/ETN/other securities excluded from ordinary-equity Silver unless historical listed/OTC membership proven.
- Historical special 5,035 cases were separately investigated: third-party exact 2,377, missing same-date archive 1,858, missing individual receipt 800 in earlier exception workflow. This is a separate historical scoped population and MUST NOT be added to current 6,691 HOLD as if disjoint.
- Repair: exact same-day portal code/date/tier matching (3 historical spot checks matched), official historical class master, deterministic totals consistency, archived independent values where service retention expired; non-retrievable stays evidenced exception.
- Official: https://www.tdcc.com.tw/portal/zh/smWeb/qryStock

## TAIFEX — historical formats and actual failures
- A: 1,254 CSV encoding+width pass but publication/PIT pending; 1,118 width HOLD; 328 date evidence; 140 ZIP; 102 ZIP expansion; 90 parsed; 73 dataset identity; 29 content-period conflict; 6 contract-month conflict. 984 formal READY.
- Deep tests isolated trailing comma versus header mismatch, repeated title/header rows, one-column footer, official report-specific schema, CP950/Big5/UTF8, ZIP size/expansion; each requires a distinct row grammar. A single generic CSV table parser is insufficient.
- Trade day and contract delivery month are different fields. After-hours starts May 15 2017 and must be attributed to applicable market trading day and session; futures, options, institutional traders and large trader data have separate file structures.
- Repair: versioned per-report parser keyed by `dlBargainOrderDown`, `largeTraderOptDown`, `productOrderDown`, `futDaily` etc, official downloaded record equal by trading date + product + contract + period + metric; do not fill mis-width cells with zeros.
- Official: https://www.taifex.com.tw/cht/4/historyOfTrading and https://www.taifex.com.tw/cht/3/futDailyMarketView

## NDC — historical formats and actual failures
- A: 319 native-cell checks pass; 1 undocumented native cell gap; D: 319 previously READY and 1 semantic HOLD. The prior deep parser treated XLSX as generic ZIP; fixed, now requires workbook/sheet/cell-aware extraction.
- Historic business signal composition/vintages must differentiate 2001-01, 2007-07, 2013-07, 2018-07, 2024-01, and older signals. Historical backfilled/revised series cannot masquerade as what was available at the trading date.
- The direct government website returned HTTP 403 from GitHub runner in one test; data.gov.tw dataset catalogue presence verifies metadata only, not the missing numeric cell.
- Repair: inspect official XLS/XLSX/PDF native worksheet and cell coordinates, effective series/method revision and original publication timestamp; if no official cell available, create documented source-level exception, not an invented number.
- Official: https://www.ndc.gov.tw/nc_335_2237 and https://www.ndc.gov.tw/nc_336_2245

## FinMind — dataset and API historical formats and actual failures
- A: 2,578 verified archive/member SHA and rows but PIT pending, 712 row-period conflicts, 359 parsed waiting origin, 37 ZIP, 14 malformed member names; 0 official READY.
- Bug fixed: stock_id exists in financial statements too, so `stock_id` must NOT imply `FINMIND_PRICE`. Exact financial `date,stock_id,type,value,origin_name` is a financial fact, not OHLCV.
- `TaiwanStockFinancialStatements`/BalanceSheet/CashFlowsStatement/MonthRevenue all have different period-vs-publication meanings; balance sheet _per columns are percentages, EPS NT$/share, financial amounts NTD (official source may be thousands); cashflow often year-to-date accumulated. v3/v4 dataset naming and history may vary. Market TWSE/TPEx vs emerging membership must be effective-dated.
- Repair: classify each dataset and field version; verify raw API receipt, member hash and row trading/reporting period; compare against respective exchanges/MOPS source with consistent concept, amount and scale; FinMind comparing itself is not an independent third party. Do not let absent paid API entitlement turn into fabricated official data.
- Docs: https://finmind.github.io/tutor/TaiwanMarket/Fundamental/ and https://finmind.github.io/tutor/TaiwanMarket/Technical/

## Engineering defects fixed or remaining

**Fixed 2026-11-16**: TWSE `www.twse.com.tw` domain recognition, categorical 成交統計 numeric false positives, B+C single-read parity smoke tests, Google Drive checkpoint transient read timeout with readback, V2 independent failed-source handling, TWSE/TPEx historical 3-way sample and TPEx moved off legacy HTML endpoint, independent 15-minute seven-way watchdog, maximum source retry count, XLSX workbook vs ordinary ZIP, nested ZIP depth cap, FinMind generic stock_id misclassification.

**Still blockers before 39,283 HOLD can be officially released**:
1. Some ZIPs lack original manifest/source provenance or contain unrecognized datasets.
2. Need full per-dataset independent official published numeric comparator for MOPS/TAIFEX/NDC/FinMind; current bridge retrieves publisher *documentation*, not original historical values for those sources.
3. Historical official material cannot always be re-downloaded (including TDCC expired query windows); supply verifiable alternate archive or explicit exception.
4. D stage currently writes `D_CANDIDATE_FULL_THREE_WAY_ATTESTED` only on full attestation, not an independent signed authoritative new release, and receipts must be cryptographically verified, not only named in booleans.
5. Completing a source parser sweep, or matching one stock's close, is not the same as full file rows/columns/PIT as-of proof. No Silver/Gold materialization is authorized without final release.
6. GitHub 15-min scheduled watchdog may be delayed by GitHub platform; each source has its own lock/checkpoint, so a failing source should not stop peer sources.

## One-click operation

GitHub Actions workflow `v097_seven_full_parser_audit_resume.yml`, action `Run workflow`, mode `audit_and_resume`: run every parser negative selftest, read latest seven-source complete frozen formal gate, generate full A/B/C/V2/DEEP/D error census and dispatch the independent per-source 15-min watchdog. `audit_only` audits without dispatch. Legacy old ready 35,467 unchanged until separately validated formal release.

The next command can restart evidence acquisition and classify all reachable HOLD partitions; **it cannot safely guarantee all 39,283 HOLD become Silver Ready** until unavailable historical originals, full numeric comparisons, PIT and formal release evidence are resolved.
