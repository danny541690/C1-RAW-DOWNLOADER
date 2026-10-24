# Schedule 6 native format repair, 2026-10-24

Revision: TAIFEX_NATIVE_FORMAT_REPAIR_V2_20261024.

Confirmed from retained failed production ZIP SHA aeb574dd711bab6aebd6c6eac58d8e2008c0047eef0ab239236b568dc8f23ac0: 2021_fut.csv ends in a standalone DOS EOF byte. The old validator treated this as a malformed trade row. The repaired validator accepts 405,797 rows, actual dates 2021-01-04 through 2021-12-30, both general and after-hours sessions, with ZIP CRC verification. Only trailing EOF/whitespace is removed for validation; native bytes remain unchanged.

Actual official POST combinationOrderDown for 2026-10-01 through 2026-10-22 returned an explicit JavaScript alert 查無資料. This is now a source-empty response, with no historical absence certification. Other HTML remains unresolved. The official CCP_CMLists API returned Swagger UI instead of JSON: retained as unresolved with a six-hour route cooldown, never counted as data.

Other changes: compact ROC and Gregorian dates; trade date cannot fall back to expiry date; one-time bounded retry migration for failed receipts; recover retained SHA-matching failed evidence before downloading; preserve all successful receipts; 15-minute per-unit retry delay and source-specific 403/429 cooldown; annual archives prioritized newest first; retain each form's declared availability bounds instead of imposing an invented universal three-year window. Status includes unresolved error counts and exhausted units.

Validation: 22 unit tests passed, plus the real retained ZIP and two live official response samples above. Remote save/readback is performed by Drive.put with direct_readback enabled. Production run and remote recovery results must be verified after deployment; tests alone do not prove full coverage, numeric correctness or PIT validity. Official endpoint errors/timeouts remain external unresolved conditions rather than falsely completed downloads.
