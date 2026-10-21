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
