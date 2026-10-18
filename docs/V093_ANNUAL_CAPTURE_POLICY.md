# JARVIS C1 v0.93 — Annual public-data capture policy
Status: APPROVED USER REQUIREMENTS / IMPLEMENTATION PENDING
Updated: 2026-10-18

## Goal
One command with a target year starts a GitHub Actions orchestration that works through January–December for the four approved public data sources (TWSE, TPEx, MOPS, FinMind), without requiring another manual instruction per month. The public repository contains code and sanitized progress only. The private `C1-JARVIS` repository retains proprietary strategy and private settings.

## Download, partition and durability contract
1. Parameter: `year` (and explicit `mode=annual|repair`, default annual once implemented). Process **content month** January to December; maintain a source/dataset/period-unit ledger within each month. Source endpoints may fetch an annual range when permitted but must partition by content month before accepting each unit.
2. For every successful source/dataset/date-or-period unit: validate basic schema, date/period, nonempty/legitimate-empty response, record source URL and fetched-at metadata; upload raw native bytes to the authorized **private** Google Drive destination `ChatGPT資料存取/C1_0.93/01_RAW/{year}/{source}/{YYYY-MM}/` and write a durable receipt with SHA256, byte count, status and attempts. Verify the uploaded bytes/hash/readback before setting `SAVED_BASIC_VALID`.
3. Preserve original response bytes; do not silently patch units, backfill zeros, re-use v0.92 raw, interpolate, or treat HTTP success as data correctness. Unverified/PIT-incomplete inputs must be marked as such and must not pass production gate.
4. The unit checkpoint/ledger must be written durably as each unit resolves, not just once per month. Persist checkpoint and monthly reports outside ephemeral GitHub Actions runners, preferably in the controlled Google Drive project structure (under `05_CONTROL` and `07_REPORTS`).
5. At **every month-end**, produce and persist `MONTHLY_PROGRESS.json`, `MONTHLY_PROGRESS.md` and `MISSING_UNITS.csv`, including year, month, source, scheduled units, verified basic saves, missing, unresolved/unverified, request counts, attempts, bytes, elapsed time, error categories and next resume position. Continue to subsequent months even when prior month finished WITH_GAPS.
6. On completion of December, publish an annual summary and a machine-readable missing/pending manifest. The annual summary must distinguish completed schedule units from full-market and PIT/numeric coverage.

## Strict bounded retry policy
1. Each failed logical unit may be **retried at most three additional times after its first attempt** during one annual run: up to four total attempts per unit. This definition avoids the ambiguity in 'retry three times'.
2. Retry transient errors (429, timeout, 5xx, temporary connection errors) using bounded exponential backoff and jitter; respect Retry-After and API quotas. Do not retry permanent errors (invalid request, unauthorized access, missing contractual data) blindly; record them and continue.
3. Never reset an in-run retry counter when resuming the same run. If retries are exhausted, mark `FAILED_RETRY_LIMIT`, append to `MISSING_UNITS.csv`, persist context and continue to other units/months.
4. Repeated systemic failures must trigger per-source circuit breaker/hold, logging unattempted units separately; no endless loops or blocked annual progress.
5. A **subsequent explicit user command** may start a separate `repair` run targeting only failed/missing/held/unverified units. That new run gets its own capped retry budget and separate audit trail. Successfully persisted, hash-confirmed units are not re-downloaded.
6. If the GitHub job nears the runner time limit or source API quota is exhausted, checkpoint and finish cleanly, and schedule another bounded job or workflow continuation once correctly implemented; do not rely on a single job lasting indefinitely.

## Failure classification and QA
Use distinct `PENDING`, `SAVED_BASIC_VALID`, `SAVED_UNVERIFIED`, `PERIOD_PENDING`, `FAILED_RETRY_LIMIT`, `SOURCE_HOLD`, `NOT_AVAILABLE`, `REJECTED`, `PIT_PENDING`, and `QA_VERIFIED` states. All source/dataset requirements require contracts, market universe coverage and PIT verification. Preserve listing/OTC/emerging classification and historical validity dates. No missing value becomes zero unless source explicitly means zero.

## Storage and public/security boundaries
- Public GitHub Actions runner may use temporary workspace and short-retention sanitized CI artifacts only. Do not commit raw market datasets, personal datasets, strategies, account configuration, Google Drive IDs or credential files to public Git history.
- Google Drive write permission is a **separate prerequisite**. Use GitHub Actions secrets/least-privilege or OIDC where possible and never echo credentials/URLs with tokens to logs. Validate upload/readback before claiming success.
- If storage upload fails, mark `NOT_PERSISTED` and do not advance checkpoint to successful; a local temporary file alone is not a durable save.
- Respect public data source documentation, licensing, fair use and API limits.

## Acceptance criteria before live full-year capture
- Four verified source adapters, documented contracts and rate handling.
- End-to-end canary month on real data with checked raw files, Drive storage readback and monthly progress/missing reports.
- Simulated transient and systematic failures, bounded retries, month progression despite gaps, runner interruption and cross-job resume, no redownload on verified success.
- Workflow starts from a single annual input and can continue across bounded jobs without repeated manual commands.
- Separate QA and production gating; no claim of completion without source evidence.

## Deployment status
This policy is a design contract only. The current `v093-annual-plan.yml` is **dry-run only**; no fully automatic four-source downloader, Drive uploader, checkpointed resumer, retry engine or auto continuation is yet demonstrated.
