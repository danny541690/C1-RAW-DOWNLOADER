# v0.93 prelaunch continuation — 2026-10-21

Requested source conversation: FinMind 2026 下載驗收. Conversation retrieval is partial; repository code and Actions logs are authoritative for executed work.

## Recovered checkpoint
- Previous code: f20af77604ade198571189fb21a8a4fa7256f98a.
- Previous Actions run: 39581487711 (7 successful jobs; regression 240 tests).
- Real sample months: 2014-04, 2024-06, 2025-01, 2026-09.
- Prior combined audit: 142 attempted members; 1,364,695 unverified numeric cells; 5 MOPS parse/quarantine errors; 7 independent close comparisons, zero mismatches. These counts do not establish full coverage or release approval.

## Work completed in this continuation
- Code 57f78ef60907ae703e4153dcce4e32d13686bceb: MOPS read-only revenue probe now recognizes stock identifiers only in the headed company-code column. Arbitrary four-digit revenue cells do not count as stocks.
- Explicit report period and monetary unit are required for revenue candidates. Decimal conversion reports amounts in NTD 100 million.
- Export dates are not publication dates. All candidates retain publication_date=null, pit_verified=false, numeric_verified=false, certified=false.
- Local full regression: 243/243 PASS. Five-stage contract check PASS for 322 descending months, 2026-10 through 2000-01.
- Cloud validation started automatically by the code changes: run 39582234666 at the above commit. Final result: SUCCESS; cloud regression 243/243 PASS. Real 2026-09 MOPS files yielded 863 + 30 + 994 + 93 = 1,980 unverified revenue candidates, zero rejected rows in those four files. These are diagnostic row counts, not certified unique-company coverage.

## Remaining checkpoint / next work
1. Inspect new real MOPS revenue candidate counts and compare exact company/period/metric/unit keys against an independent source; do not publish diagnostic candidates.
2. Preserve isolation of the TWSE-prefixed member inside the MOPS archive (SOURCE_PATH_MISMATCH_MEMBER_PREFIX).
3. Obtain company-specific publication/version evidence for PIT; export date alone is insufficient.
4. Resolve TWSE corporate-action members with zero cells and source archives missing from bounded historic samples.
5. Implement and validate real RAW, QA1, PRICE, FINANCIAL, CHIP processing paths. Current five workflow files are prelaunch stubs; shared concurrency and dependency contract tests do not prove production readiness.
6. A comment-only retired v093-queue-stress-trigger.yml still produces invalid-workflow failures; this is separate from the parser acceptance run and must not be counted as a passed stress test.

Release remains BLOCKED. No cron activation and no production Drive writes were performed by this continuation.

## Second continuation — cross-source metadata guard
- Code commit: 18d08d059ae1332df479b1130bd0065e912a59c1.
- Found and fixed: assess_evidence previously checked presence of comparison metadata without verifying equality against the primary company, period, metric and unit. It also accepted missing independent source and arbitrary digest strings.
- Comparability now requires exact identity/semantic/unit agreement, an explicitly supplied primary metric, a different nonempty source, a 64-hex source digest and complete primary evidence. Metadata agreement alone still leaves verified=false.
- Local full regression: 247/247 PASS; five-stage workflow contract remains BLOCKED with no cron.
- Cloud run 39588075481 completed SUCCESS: 7/7 jobs; 247/247 regression tests; all four real-data months completed. Combined audit remains BLOCKED: 142 members, 1,364,695 unverified cells, 5 MOPS quarantine/parse errors, 7 close-price comparisons with zero mismatches, missing bounded historic MOPS/FinMind archives, unmapped/empty members and unconnected five-stage production implementations. Production Drive writes=0.
- These checks exercise the evidence guard. They do not verify real financial values or establish company publication dates. Prior real source-coverage and five-stage implementation blockers remain open.

## Third continuation — conflicting price-key isolation
- Code commit: fa8ef228a96667a238108273b14051f2b875c87e.
- Found and fixed: a source with contradictory prices for the same stock/date was counted as a duplicate conflict but its first value could still participate in cross-source agreement. Conflicted source keys are now excluded permanently for that comparison, independent of row order; clean independent sources remain comparable.
- Canonical ISO dates, string security identifiers and finite nonnegative nonboolean tolerances are required. Identical duplicates do not inflate pair counts.
- New adverse tests cover all permutations of a conflicting triplet, unaffected independent sources, exact duplicates, invalid keys and unsafe tolerances.
- Local full regression: 252/252 PASS. Five-stage workflow contract check PASS; release BLOCKED, no cron or production Drive writes.
- Cloud run 39590624849 completed SUCCESS: 7/7 jobs, cloud regression 252/252 PASS, four real sample months completed. Combined bounded sample audit remains 142 members, 1,364,695 unverified cells; seven close-price pairs agree with zero duplicate conflicts. Five MOPS parse/quarantine errors and previous coverage/PIT/implementation blockers remain; production writes=0, release=BLOCKED.
- This fixes diagnostic comparison safety; it does not approve MOPS revenue, establish PIT availability or complete real five-stage production paths.

## Complete audit continuation — authoritative current checkpoint
- Complete run 39596112752: 14/14 jobs PASS; regression 257/257 PASS; all 322 months inventoried again.
- Current inventory: 1,288 source-month pairs; 690 empty, 598 file-present/unverified; 7 duplicate-name issues; 15,783 files; no zero-byte files.
- Actual per-run GitHub/Drive sandbox process crash, cross-job resume, real-time expiry, fencing and concurrent CAS collision PASS. This does not connect the five production workers.
- Invalid retired queue trigger is removed; three legacy queue-stress diagnostics are manual only.
- Exact remaining OP-01..OP-05 and DATA-01..DATA-02 requirements: docs/V093_PRELAUNCH_READINESS_20261021.md.
- Do not conflate historical backfill completion with RAW operational launch readiness. Next substantive work: implement/connect real stage workers and their durable handoff, then test production-path cancellation, cutover and sustained load.
- No production cron activation or approved-data publication occurred.

## User-adopted rules — 2026-10-21 (current execution authority)
- User explicitly adopted all recommended five-stage download rules and requested Google Drive/GitHub/cross-chat persistence.
- Authority: docs/V093_FIVE_STAGE_DOWNLOAD_RULES_20261021.md and config/v093_five_stage_policy.json; version V093_FIVE_STAGE_DOWNLOAD_RULES_V1_20261021; SHA256 c8616b51bee97ed165a38a9f4303b3e867c4df4d84d50f7f6a2d1076738dd179.
- Public downloader code commit 651915e6f08368e7efcf1c9cda53c0e745d13299; private C1-JARVIS adoption commit a997d9252ecfc883e4dc14978632ab9da9c5ef3e.
- Google Drive policy document and machine JSON created; existing config, monthly capture rule, README and cross-chat continuation updated in place. Machine JSON/config/rule/continuation byte readback matched local saved bytes.
- Cloud run 39606989385 completed SUCCESS: 263/263 tests and all five prelaunch stages load one policy digest, total request-attempt limit 4.
- Known incompatible legacy capture CLIs blocked before startup; code evidence signature now includes the policy config.
- Cross-chat summary: docs/CHATGPT_MEMORY_POINT_V093_20261021.md. A saved handoff document is not ChatGPT built-in permanent memory.
- Formal five-stage worker integration, partition concurrency/quota enforcement and production-path operational acceptance remain pending. No schedule activation or market-data capture occurred during this rules update.
