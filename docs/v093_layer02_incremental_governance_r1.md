# C1 v0.93 — 02_STANDARD 多來源增量與核准規範 R1
狀態：**設計規則已納入程式庫；正式 Golden Copy 仍為 BLOCKED，必須經過測試及來源/欄位核准。**
適用：2025–2026、未來 FinMind Backer／Free、XQ 授權補充及所有其他來源。保護現有 01_RAW，禁止以新資料靜默覆寫。

## 一、五項固定規則（與 2026-10-19 討論一致）
1. **SHA-256 與斷點續作**：以 source/dataset/native_file_digest + adapter_version 的 content fingerprint 決定是否須轉換；完全相同跳過。相同位置原文變動記為新 raw observation/version，不刪舊資料。
2. **多來源版本與血緣**：同 `market, instrument_id, observation_date/period_end, field, as_of` 可存在多來源候選。保留來源、端點與授權、取回時間、原生單位、SHA、member、row/column/資料集、adapter_version、knowledge/available_at。來源各自檔案不去重為單一列。
3. **增量轉換與依賴重算**：新檔僅轉換受影響來源/月份/資料集；變動會透過指標依賴圖標記 DIRTY，納入歷史暖機視窗、月營收 24 月視窗、季財報 TTM及跨月受影響視窗。對 unknown/unbounded dependency 不推測短窗口，全部標為待評估。
4. **Golden Copy**：轉換成功 != 數值核准。只有已核准的來源契約、欄位 schema、單位、有效股票母體、日期/PIT/公告日期及必要的比較，才可選取 candidate。主來源優先但不可壓過明確的品質 FAIL；衝突超容差 -> CONFLICT/QUARANTINE，不平均、不補零、不以多數票代替來源檢查。僅存 staging 時不得發布 approved view。
5. **Generation 與原子發布**：把新 Parquet 當不可變 generation，manifest 列明 digest、schema/adapter/QA 版本、input digests、row count、null、uniqueness、source/period/coverage。readback SHA/Parquet row count、PIT/QA gate 通過後才可透過單一 release pointer CAS 更新 active release；失敗保持前一版。Reader 固定 release_id，rollback 指向歷史完整 generation，絕不覆寫 RAW。

## 二、資料分層
- `01_RAW/{year}/{source}/{year-month}` 原生永久留存；來源歷史修訂加新觀測版本
- `02_STANDARD/{year}/{year-month}/{dataset}/{market}/{generation}`：候選資料與 Approved View 嚴格區別，初期 `NATIVE_STAGING_R2` 均為 `STAGING_UNMAPPED`。
- `05_CONTROL/SourceContracts` 欄位授權/配額/更新時間/主備來源；`05_CONTROL/STANDARD_QA` QA/衝突/缺漏；`05_CONTROL/RebuildQueue` DIRTY；`05_CONTROL/Releases` current/past release manifest。
- `03_FEATURES` 僅使用核准 release snapshot；受影響指標/日期重算。歷史當時不可知的值不得用最新修訂回填。
- `00_INBOX` 存跨月回應／隔離，與 RAW 保留原始完整 bytes 的血緣。

## 三、來源模式
- TWSE／TPEx／MOPS：原則主來源，依資料集決定 authority。
- FinMind：包含付費 Backer 歷史回補，重新映射成 **FinMind** source、保存 dataset/plan/license；Free 不可存取之 dataset 到期後標失效，不假裝繼續更新。
- XQ：補主力／分點／海外等授權可匯出欄位；分點與一般法人明確區分；沒有實測合法可匯出前不可宣稱全量。
- TDCC：按週更新，並不因股票 daily 無資料就填零。
- 相同上游的兩個轉售/二次加工供應商不能當作兩份完全獨立的真值驗證。

## 四、需要正式完成的驗收關卡
- 對 2025/2026 全年每月、每 source、每 dataset 逐檔列出：已轉、隔離、未映射、發行/交易日、實際股票數、應有母體覆蓋、重複／修訂、PIT、schema及 Golden Copy 候選。
- 不允許只憑 GitHub Actions 成功、Parquet 行數或 443 個 ID，就把品質升級 PASS。
- 先從 2025-01、2026-09 做 schema/日期/版控 Golden Golden 小規模驗證，再擴大；允許不同來源或資料集獨立 PARTIAL。
- 新增來源必做 source contract、parser fixtures、unit/sign/ROC 日期、golden、PIT及 regression test。
- 本規範不會自行批准任何欄位、任何財報 PIT、任何 443 指標公式。
