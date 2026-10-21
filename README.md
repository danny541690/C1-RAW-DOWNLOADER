# C1 RAW DOWNLOADER (JARVIS v0.93)

Public-source ingestion runner. This repository is PUBLIC. Do not put investment strategies, personal holdings, access tokens, Google Drive identifiers, or proprietary QA rules here.

## Current binding execution rules (2026-10-21)

The user-adopted policy is [V093_FIVE_STAGE_DOWNLOAD_RULES_20261021.md](docs/V093_FIVE_STAGE_DOWNLOAD_RULES_20261021.md), with machine-readable authority in [config/v093_five_stage_policy.json](config/v093_five_stage_policy.json). It supersedes conflicting legacy order/whole-month-skip/retry/top-up rules. Five prelaunch workflows load its version and hash; incompatible known legacy capture CLIs are blocked. Real five-stage worker integration and operational acceptance remain pending. No schedule activation or market-data download is performed by policy adoption.

Cross-chat handoff: [CHATGPT_MEMORY_POINT_V093_20261021.md](docs/CHATGPT_MEMORY_POINT_V093_20261021.md).

The bootstrap descriptions below are historical implementation notes; use the policy and current acceptance checkpoint for present status.

## Separation
- Private: `danny541690/C1-JARVIS` (investment models and proprietary research)
- Public: this repository (public data adapters and generic raw capture checks only)

## Current status
**BOOTSTRAP / DRY-RUN ONLY.** The included workflow validates an annual capture plan and publishes a manifest; it does **not** download market data, upload to Google Drive, or run unattended yearly backfills yet. Do not interpret a passing workflow as verified market data.

## Workflow
Actions -> `JARVIS v0.93 Annual Capture Plan` -> Run workflow -> enter year. Default `dry_run=true` is mandatory until source adapters, secrets and source contracts are verified.

## Proposed source coverage
TWSE, TPEx, FinMind, and fourth source **PENDING source-name and licensing/contract validation**. Any unimplemented source must be explicitly marked BLOCKED (never PASS).

## Storage and quality
Future raw datasets must be partitioned by year/source/month in an authorized private Google Drive destination, with manifests, SHA256 checksums, row/date/schema checks, PIT release-time tracking and resumable checkpoints. Existing C1 v0.93 raw data MUST NOT be carried over from prior versions. No credential may appear in public workflow logs.
