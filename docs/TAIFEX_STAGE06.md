# Independent TAIFEX stage 06

Verified official-source catalogue: 2026-10-23. Target: latest available October 2026 trading date descending to 2000-01-01, within each table's public availability.

- Futures daily-market annual downloads: menu reaches 1998; worker stops at 2000. Actual 2000 native ZIP was downloaded, CRC checked and its 4,065 rows span 2000-01-04 through 2000-12-30.
- Options annual downloads: published menu reaches 2001. Do not fabricate a 2000 option archive.
- Current-year market history: monthly official CSV, commodity_id=all, covering all returned products, maturities, strikes, calls/puts and general/after-hours sessions.
- Institution contract/date download forms: verified public interval 2023-10-22 through 2026-10-22, rolling three years. Older paid history excluded.
- Prior 30 trading-day native tick ZIPs: futures, options, calendar-spread trades, spread-order reports; retain both native RPT and CSV when published. Published daily Delta CSV files are also captured.
- Every GET dataset advertised by the official OpenAPI (135 in the verified catalogue) is captured as its native response. This includes market reports, institutions, large traders, settlement, margins, adjustments, FX rates, contract/product metadata and exchange/broker statistics. These snapshots do not support invented historical date arguments.
- Other official download forms are discovered independently. Confirmed date bounds are respected. Unconfirmed boundaries and unsupported non-date forms remain visible in the control record; their history is not certified complete.
- Future-dated links in a source page are excluded until their date is within the requested window. Source Date fields may describe a future effective date; these never expand reported historical coverage beyond today.

## Persistence and recovery

Workflow: .github/workflows/v093-taifex-independent.yml
Worker: scripts/v093_taifex_independent.py
Verified availability catalogue: scripts/taifex_verified_catalog.json

Cron */10 * * * *. Each scheduled wake preserves a running worker; deployments may replace it to apply a fix. A worker processes up to 45 minutes with a 60-minute job limit. GitHub scheduling and runner queues can delay actual starts. Resume uses Drive CURSOR.json; successful receipts are skipped. Each unit gets at most three attempts, then remains UNRESOLVED while other units proceed. A 403/429 applies a 15-minute backoff.

RAW root: 1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn / YEAR / TAIFEX / YYYY-MM. Annual original ZIPs use YEAR/TAIFEX/_ANNUAL with their actual year-range metadata. Control folder: 1fNIF2P4wYiGtLDrNf8tE2_0fSbWDm6gp.

SHA256 names and readback hashes protect immutable source RAW. CSV date/schema checks, ZIP CRC/content-date checks and JSON shape checks are basic verification only. Numeric correctness, PIT and complete source/category history remain uncertified. HTML/error responses are quarantined, not counted as successful data.

The cloud website catalogue initially timed out. A catalogue verified independently from official pages and real downloads now lets reachable official APIs continue; website and historical units retry independently. Some advertised API routes return Swagger HTML rather than JSON, and are explicitly unresolved. No completion claim is made for these units or inaccessible/paid historical data.
