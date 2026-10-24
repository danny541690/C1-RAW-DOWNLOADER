# TDCC timeout repair — 2026-10-24

Confirmed three unresolved history receipts, each with one attempt and TimeoutError:The read operation timed out: DESC 2026-10-16/3629; ASC 2025-10-31/2404 and /2478. These are transient source reads, not schema errors. Fresh GET-form/POST queries returned 16 validated distribution rows for each in 12–14 seconds. Local probes are not remote saved evidence.

Fix: due unresolved receipts precede new security candidates on resume; retain 15-minute retry cooldown and total cap of three, extending each source read timeout from 22 to 40 seconds with 100-second shutdown reserve. Reset the session after transport errors and record GET form, POST query, OpenAPI or persistence phase for diagnostics. Keep history completion revision V4 unchanged so visited dates, successful SHA receipts and date frontiers are not reset. Status adds transport revision TDCC_TIMEOUT_PRIORITY_RESUME_V5. No changes to data validators or date partitions.

Both TDCC workflows run all repository tests before capture. No success re-download or overwrite. Exact source-empty responses remain distinct from timeouts and do not establish complete historical absence.

Requested-history clarification: ASC still requests 2000-01-01 toward 2026. Official menu inspected on 2026-10-24: 2025-10-31..2026-10-22, 51 dates. Actual 2330 POST probes for 2000-01-07, 2013-01-04 and 2020-01-03 each returned exact official no-data responses; this does not certify absence from other official archives. Status now explicitly records requested scan start, assigned partition, source menu bounds and the unoffered 2000-01-01..2025-10-30 interval as not downloaded/other archive required. No fabricated weekly dates or coverage. Full suite: 631 passing tests.
