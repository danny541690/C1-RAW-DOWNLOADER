# JARVIS v0.97 Bronze-first implementation plan v1.1 (2026-11-10)

Status: USER-APPROVED SCOPE FOR PLANNING ONLY; NO Silver/Gold launch; NO Bronze copy implicitly authorized by this document.

## 0. Frozen priority and prohibited work
- PHASE 1 ONLY: verify v0.93 RAW candidates, recover confirmed errors, safe copy passed files into v0.97 Bronze, independently verify destination, add XQ manual CSV and FinMind 699 eligible historical raw, then close Bronze v0.97 at an explicit cutoff snapshot. User confirms snapshot before PHASE 2.
- PHASE 2 STOPPED: do not run Silver normalization, PIT feature availability transforms, Gold 400+ indicators, backtest, or BSG pipelines. No premature transformations.
- v0.93/01_RAW is immutable. Never silently overwrite/move/delete; exact copy of raw bytes only. Bronze itself is immutable/append-only with versioned corrections; no normalizing to 億元 at Bronze.
- Distinguish three kinds of validation: (A) RAW file integrity, (B) Bronze dataset identity and coverage, (C) Silver semantic numerical PIT checks. A/B failures must not be counted as C defects or vice versa.
- Each current source role separate: six official datasets TWSE, TPEx, MOPS, TDCC, TAIFEX, NDC; XQ manual and FinMind supplementary are separate source namespaces. XQ/FinMind must not overwrite official originals. Only TWSE/TPEx stock universe; daily and coarser (monthly/quarterly/yearly) allowed; no trade-by-trade/intraday.

## 1. Audit of today’s evidence
- 2026-11-09 inventory: 83,249 files indexed, 976 excluded controls, 82,273 v0.93 original candidates. Candidate count IS NOT expected historical source-calendar coverage and NOT count of proven-correct originals.
- R3 frozen issue list 73,146, processed 73,146, pending 0 at run 42826527263. RAW basic candidate: 7,136; legacy statuses to evidence-reconcile: 65,991; blocked large files: 19. Those categories cover 73,146 but are NOT 82,273 inventory pass/fail. Need reconcile the remaining original candidates from non-R3 receipts.
- Historic R3 “ZIP_MEMBERS_PARSED_SOURCE_SCHEMA_PENDING”, “TDCC_IDENTITY_MISSING...”, “PIT_OR_DOCUMENT_RULE_PENDING” etc are NOT confirmed corrupt raw bytes. Do not rescan all files or claim “100% Bronze pass” from completed R3 ledger.
- Existing GitHub scripts currently implement metadata inventory, R2/R3 receipts and rudimentary structural checks; they DO NOT demonstrate an accepted 0.93→0.97 copied Bronze population or 1:1 source-destination hash evidence. Explicitly block copy until gate/code validation.

## 2. A: v0.93 RAW certification (only original)
A0 Frozen inventory manifest: source Drive ID, full path, name, dataset, source date, version, original byte length, available MD5, computed SHA256, evidence refs, tested rule-version, work status. Match every unique inventory ID and R2/R3 statuses, avoid duplicate or stale evidence.
A1 Use existing verified actual-byte/CRC/hash receipts if complete and SHA-matched; no automatic A_PASS on parser syntax or old PIT pending labels. For missing evidence, bounded raw-only read and verify syntax/CRC/size/source identity and date consistency. Do not mix Silver schema.
A2 Capture unknown/NA/not-published/source-unavailable separately using source publication calendars, not blanket “missing”.
A3 Confirmed corrupt only: diagnose, max three safe attempts, source-specific reacquire exact dataset and period into quarantine candidate; test again and compare. Never alter source file or substitute FinMind as original official bytes.
A4 Stage-A gate: PASS, PARTIAL, CONFIRMED_NG, QUARANTINED, BLOCKED, NOT_APPLICABLE, NOT_YET_PUBLISHED, MISSING_CONFIRMED. Only A_PASS with SHA+source ID+verification receipt can copy. All errors persist in ledgers and are visible.

## 3. M: controlled copy v0.93 → v0.97 Bronze
- Destination root: ChatGPT資料存取/JARVIS_C1_v097_LIFECYCLE/02_DATA_LAKE/01_BRONZE_ORIGINAL with source/dataset/year/month partition only after checking existing taxonomy. Do not create competing roots.
- Copy only explicit A_PASS manifest. v0.93 source immutable and v0.97 destination append-only. Preserve exact bytes and source name; write sidecar manifest outside immutable raw.
- Use approved sourceID+SHA+target key for idempotency; target same hash=SKIP_IDENTICAL; same name different hash=HALT_CONFLICT; no overwrite. Use per-target single-writer + checkpoints, atomic staging/publish or uniquely identified versions, post-copy re-read SHA and size; timestamp and run ID; independent source↔destination receipt.
- Counts conservation: approved = success + skipped-identical + failed-or-blocked, no double counts; exceptions do not block unrelated files. Bounded copy test (e.g. samples per source and format) and failure injection before bulk.

## 4. B: independent v0.97 Bronze second acceptance
- Verify destination by independent enumeration and bytes/hash, approved source mapping, source/provider/dataset/period path, duplicates/collisions and archive/readability, source-calendar coverage where verifiable.
- Bronze keeps each source native original, with metadata describing retrieval datetime, official/publication date if available, URL/API endpoint, license/terms and raw source version; no cross-source overwrite or premature merging.
- Important two gates: B1 byte-provenance PASS (exact original copy SHA) vs B2 source/dataset/period coverage/quality PASS. Dataset numerical semantic checks limited to clearly defined Bronze contract; do not reject valid native raw merely because Silver schema/PIT is pending.
- Per partition outputs BRONZE_PASS / PARTIAL / BLOCKED / NG + exception ledger; no Silver export regardless.

## 5. XQ Manual Bronze onboarding
- XQ manual data is its own namespace: original exported CSV bytes + SHA, filename, export datetime/timezone, report end trading date, script version, field names, units, export operator and lineage.
- Validate file readable, expected columns, export completeness/row headers/date, stock code format, date windows, duplicated codes/dates, unintentional Excel scientific notation and encoding; retain user original file unchanged.
- XQ overlapping batches and columns remain separate immutable raw versions; only record duplicates/overlaps in Bronze index, do not average/merge/normalize fields now.
- Currently optional missing XQ indicators tagged PENDING_SOURCE, not zero and not Bronze corruption. No broker detail if not provided; avoid accidentally requiring Top15 per-branch details when not intended.

## 6. FinMind 699 Bronze onboarding
- Payment/plan and endpoint permissions are NOT assumed; confirm actual 699 entitlements, exact datasets, licenses and rate limits at onboarding before implementation.
- Download only explicitly needed missing historical datasets/date partitions after official-source coverage audit, preserving FinMind as independent licensed source. Never overwrite or impersonate official original. Record API endpoint, params, retrieved_at, period, symbols, pagination, status code, token scope, SHA and data vintage when provided.
- Resume by dataset/year/month checkpoints; bounded backoff/rate limit; confirm API success vs HTML error/empty response; detect incomplete pages/date truncation; compare with known official dataset only at quality metadata level. FinMind availability must not be inferred just from payment.

## 7. Bronze cutover acceptance
- Freeze explicit historical data cutoff date and edition/revision ID. “All Bronze complete” means all datasets in an agreed published scope are PASS or documented accepted exemptions; not “forever every future day”.
- Three Bronze channels have valid independent QA: official(v0.93 carryover + safe official gap acquisitions), XQ manual, FinMind supplemental.
- Independent exhaustive manifest reconciliation by source/dataset/year/month, SHA/provenance, gaps, policy NA, duplicates, conflicts, retries and quarantine; audit old→new source lineage, no unauthorized transformations.
- Lock a versioned “BRONZE_RELEASE_MANIFEST” only if all required scope gates pass; user explicitly authorizes Silver later. Future daily incremental Bronze is allowed but should be a new release/version and can later trigger delta Silver, not silently change frozen historical Bronze.
- No Silver or Gold Actions workflow should write during Phase 1. Disable their schedules at the scheduler layer when authorized, but do not silently delete workflows/code.

## 8. Scheduling for fastest safe completion
- Preserve useful 12 shard QA receipt structure and incremental checkpoint, do NOT restart all R3 as “not complete” because it is already done.
- Suggested queues: A1 reconciliation (parallel read-only), A2 issue-specific RAW only rescan and bounded repair, M1 single-writer partition-safe copies, B1 destination QA independent; XQ intake and FinMind intake operate as separate source queues only when user provides XQ files/purchased FinMind access.
- Dependency per immutable file: A_PASS→M_HASH_MATCH→B_HASH_AND_IDENTITY_PASS. Maximum parallel constrained by Drive API quota and target writers; tune from measured throughput/errors, not arbitrary maximum.
- New audit output each batch includes total inventories, raw A_PASS/PARTIAL/NG/BLOCKED, copy passed/failed, Bronze passed/partial/exception counts, XQ waiting, FinMind waiting, run ID, SHA and verified snapshot timestamp.
- Fail closed on corrupted/frozen manifest or race, retries 3 and quarantines on case-level errors, no endless loops. No claim of actual execution absent Run ID.

## 9. Defects and improvements found in proposed process
1. “RAW pass then copy” must have precise file ID+SHA evidence; parser-only receipt is not enough.
2. “100% processed 73,146” means R3 queue processing, not 82,273 file certification.
3. Original 82,273 are existing Drive files, not source-calendared 2000-2026 complete inventory; add published-source calendar audit.
4. v0.93 → v0.97 “move” should be immutable copy and verify, never move.
5. Double verification must be independent destination hash, not only same receipt reused.
6. FinMind not necessarily same schema, source, vintage or license as official; separate namespace and retain native form.
7. XQ manual partial dates and export script versions can cause hidden history gaps; versioned intake and date-window coverage required.
8. Overlap source precedence is a Silver/future curated projection policy; Bronze preserves all raw variations.
9. “Only start Silver after Bronze is complete” needs a defined snapshot cutoff date and required datasets; otherwise daily market updates make completion impossible.
10. FinMind historical add-on and XQ arrive at different times; accept independent partition gates and finalize when user explicitly approves both. No repeated total Silver rebuild because Silver not started.
11. Bronze raw original may be incomplete even if structurally parseable; indicate partial coverage and do not certify full market completeness.
12. Avoid future information bias: record as-of/publication and retrieval dates in Bronze provenance, perform PIT semantic logic later in Silver.
13. Storage/cost: if identical byte content duplicated in Drive, consider immutable content-addressed alias ONLY if clear traceability and backup needs; do not silently use shortcuts.
14. Administrative controls must distinguish quarantined data from legally/technically unavailable datasets and from user-deferred indicators.

## Decision
PHASE 1 = RAW verify, recover/quarantine, exact copy to Bronze, independent Bronze verification, XQ onboarding, FinMind 699 onboarding, source coverage and lineage freeze. PHASE 2 = Silver/Gold remains OFF until user explicitly requests, after snapshot acceptance.
