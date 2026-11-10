# JARVIS v0.97 Bronze-first autonomous runbook R4
Date: 2026-11-10 Taipei; only v0.93 immutable RAW -> v0.97 Bronze. No Silver/Gold.

## Updated production pipeline
1. Preflight and existing R2 audit reuse; 12 RAW rescue lanes for missing receipts.
2. Six SHA guarded copy lanes, six independent fresh-read destination SHA/name/actual-folder QA lanes.
3. Single-writer segregation of accidentally copied control receipts outside Bronze, revoking affected QA approvals.
4. Aggregate immutable receipts and checkpoint conservation, immediately self-dispatch another batch when pending > 0.
5. Read-only 15-minute recovery watchdog notices stalled success/failure and re-dispatches when no active run and pending remains. Three consecutive system failures stop as a safe exception, not a fabricated success.
6. Stop ongoing schedules after zero locally actionable pending. No hourly main cron.
7. Legacy invalid R3 workflow removed from active Actions directory after preserving exact code in governance/v097/archive/v097-issue-repair-12-lanes.DISABLED.yml.txt.
8. Independent merged acceptance reports fail-closed source/copy/QA/control-sidecar/conservation checks. No Silver/Gold.

## Historical counters are NOT final certification
Existing v0.93 inventory: 82,273. R2 basic-byte candidates: 73,376; 7,767 missing receipts, 1,104 quarantined, 19 path conflict, 6 unknown source, 1 parser/size blocked. These are snapshot classifications, not full 2000-2026 expected source availability.
RAW rescue examines original bytes/structure/source identity without mutating v0.93 and records full SHA or block reason. Original preexisting quarantine or conflicts are NOT silently considered clean.
Per-file Bronze byte provenance PASS is not same as financial semantic validity or per-source historical coverage PASS.
Source/date market publication calendar completeness, genuine financial data quality, and manual exception resolution/acceptance still require evidence.

## External-source gates
XQ CSV cannot be ingested until authentic manual exports are supplied. FinMind 699 cannot be ingested without active entitlement, API and dataset scope. Both are WAIT_EXTERNAL, not considered completed.
No silent Bronze merge/dedup of official, XQ and FinMind raw data; keep all three namespaces distinct.
Only user-approved Bronze source-coverage release may permit later Silver / Gold.

## Run semantics
GITHUB_SUCCESS = steps ran, not Bronze certified.
RAW_BASIC_CANDIDATE = suitable for SHA/identity guarded copy if all candidate evidence holds, not full market correctness.
BRONZE_BYTE_PROVENANCE_AND_PATH_PASS = original bytes and actual destination agree; may be revoked if discovered to be nonmarket control.
COMPLETED_WITH_DOCUMENTED_EXCEPTIONS = automated queue exhausted but source coverage or external inputs remain outstanding.
BRONZE_RELEASE_ACCEPTED = separately verified and explicitly approved, never inferred from zero queues.