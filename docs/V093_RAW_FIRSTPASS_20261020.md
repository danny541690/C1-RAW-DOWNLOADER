# RAW first capture only: 2026-12 to 2000-01

One replacement workflow; all earlier workflows remain disabled. Exactly 324
month slots in descending order. Future months are recorded NOT_AVAILABLE, current
month is through execution date only. No automatic later top-up of these months.

Existing means any native-data file in any of the four v0.93 RAW source/month
folders. Such a month is skipped as a whole, with file IDs/counts recorded. This
is deliberately conservative: it neither certifies completeness nor fills missing
sources in a partially populated month. Inventory errors are recorded and skipped.
No old-version import, RAW modification, STANDARD conversion or gap repair occurs.

For new months the official TWSE/TPEx daily/event and MOPS revenue/quarterly-group
capture contracts are reused. Two simultaneous HTTP calls at most. Financial codes
are provisional observed stocks, not a verified historical universe. Calendar is
not certified, and holiday empty responses are explicit unresolved results. FinMind
is not called: it was configured as gap supplementation and this run forbids that.
Every unit gets durable request intent before HTTP. A failed or interrupted intent
is never automatically replayed. Bytes that fail basic validation are quarantined.
Successful native ZIPs get CRC and remote SHA readback checks. Drive persistence
transport recovery may retry a save; source data requests are never logically retried.

Control folder: 07_REPORTS/RAW_FIRSTPASS_202612_TO_200001_V1. PLAN.json, CURSOR.json,
PROGRESS.json and per-month MONTH_STATE.json/RESULT.json preserve policy, evidence,
errors, unknown interrupted requests and archive hashes. GitHub batch summary and
FIRSTPASS_ALERT logs identify months requiring the user's separate repair schedule.

Cadence: UTC minute 11 and 41, 40-minute worker, one active writer with checkpointed
continuation. When all slots are processed the workflow disables only itself.
Completion means processed or skipped with recorded gaps, never certified coverage.
