# Sole independent RAW schedule: latest 2026 data to 2000-01

This replacement supersedes both the capture-only 2026-2000 proposal and the
2025-2000 proposal. On deployment it disables all other repo workflows and waits
for their queued/active runs to stop before source access. Other STANDARD, feature,
repair, controller and old capture workflows remain disabled.

Scope is frozen at first launch to the current Taipei month (2026-10 at deployment),
then strict descending months through 2000-01: 322 months. PLAN.json records the
as-of date. Current month is explicitly partial; future months are not fabricated.
One active writer, 40-minute work budget, 55-minute job, UTC minute 13 and 43 cron.
The next cron resumes durable inventory/unit/month cursors without user commands.

All input/output stays in the v0.93 RAW root under year/source/month. Existing
actual bytes are inspected: archive CRC, manifest member hash when present, source
and payload date, stock identifiers and basic price OHLC. Only proven source/date/
dataset units are reused. Unknown metadata is not a completeness certificate.
Conflicting revisions stay visible. Existing bytes are never deleted or replaced;
invalid response bytes are kept in a separate control quarantine.

Primary source contracts: TWSE and TPEx prices, indices, institutional, margin,
lending, valuation, foreign holdings, market cap and corporate-action events where
supported; MOPS monthly revenue plus observed-company quarterly income/balance/
cash-flow groups. Historical stock universe, trading calendar, source field units,
all 443 indicator inputs, disclosure PIT and source coverage are not fully certified.
RESULT.json must continue to display these limitations, never full-market PASS.

New or missing official source units get at most three total source attempts. The
attempt number is persisted before HTTP and survives restarts. Unsuccessful units
then remain recorded and are not retried indefinitely. Drive save/readback transport
recovery is separate. Null/invalid price cells are flagged separately from confirmed
OHLC violations; missing values are not replaced with zero.

FinMind FREE supplements explicit official gaps; no paid subscription is used.
Original source values are never silently patched or mixed across definitions.
Supplements have stock/date/envelope validation and price OHLC checks. Pending tasks
respect the shared quota ledger, do not block primary month progression, and drain
from an automatic persistent backlog after the primary pass. Each supplement also
has a three-attempt bound. Unsupported categories and exhausted failures remain
unresolved in MISSING_AND_PENDING.json. Trading-date-unproven tasks are not treated
as confirmed data. Raw response validation is not an independent numerical Golden
or production acceptance.

Control: 07_REPORTS/INDEPENDENT_RAW_2026_LATEST_TO_200001_V1. Each month saves
MONTH_STATE.json, RESULT.json and MISSING_AND_PENDING.json; root saves PLAN.json,
CURSOR.json and PROGRESS.json. GitHub summaries and INDEPENDENT_RAW_ALERT log lines
report problems without starting any separate repair workflow. Completion disables
only this replacement workflow after bounded supplement processing.
