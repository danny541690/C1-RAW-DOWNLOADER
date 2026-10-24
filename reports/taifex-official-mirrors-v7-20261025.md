# TAIFEX schedules 6 / 6-1: verified official CSV mirrors V7

2026-10-25, Asia/Taipei. Extends V6.1; does not certify full history, numeric semantics or PIT.

## Confirmed source defect and repair

OpenAPI routes return Swagger HTML for some documented datasets. Government open-data catalogue links identify working TAIFEX native CSV resources. Only two independently live-probed routes are enabled:

| Route | Official catalogue | Native rows | Actual content date | SHA256 |
|---|---|---:|---|---|
| AcceptableCollateralGovernmentBonds | https://data.gov.tw/dataset/11351 |149|2026-10-23|c5bbed3a67aee933417443b1e8b83ec9f8600391ba836a4ecb12459f7c9cb03b|
| IndexFuturesAndOptionsMargining | https://data.gov.tw/dataset/11604 |31|2026-10-22|ce9ff6ac3244dee38283e3bbe737e5de5e843e37c570bbcfb133ded43abe5068|

Resource pattern confirmed by the catalogue: https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=AcceptableCollateralGovernmentBonds (and IndexFuturesAndOptionsMargining).

Exact Chinese headers, row widths and actual source dates are validated. Bytes are preserved. The existing immutable RAW save and remote SHA readback remain mandatory. Requests retain both the logical API job and actual official CSV source/catalogue URL.

The mirror applies only to a capture job for the current local day. Old missed snapshots remain unresolved; current data cannot recreate a past capture. A one-time migration reopens only today's known Swagger failure on these verified routes, retaining prior attempts/error history. Valid saved receipts never reopen. Mirror routes use their own route cooldown and respect the actual TAIFEX website host cooldown.

## Remaining issues and treatment

- Other Swagger routes: retain unresolved; do not invent equivalent URLs or widen schema acceptance. Expand only after official mapping and actual-body verification.
- Past interrupted snapshot: retain missed capture; no fabricated historical parameters.
- HTTP 520/timeouts: existing bounded transport retry cycles, host cooldown and alias recovery continue. No unlimited retry.
- Source empty / unavailable historical interval: distinct terminal records, not proof of complete historical absence.
- Tick availability limited to published recent files: collect available files; old absent ticks remain gaps.
- Accounting/numeric/PIT and total dataset coverage: remain unverified despite a successful transfer.
- Schedule 6-1 imports verified history catalogue and works 2000–2012; current snapshots belong to schedule 6. Both execute the shared corrected implementation.

Prior complete issue inventory: reports/taifex-v6-two-day-problems-20261025.md.

Community implementation examined for CSV-vs-JSON and website download approaches: https://github.com/twjackysu/TWSEMCPServer/blob/main/CLAUDE.md . Production mapping is grounded in the official catalogue and live source bytes, not community assertions.
