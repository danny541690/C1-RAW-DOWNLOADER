# JARVIS C1 v0.95 — 2026-09 第一階段遷移 / Bronze Silver Gold 驗證

核對日期：2026-11-06（Asia/Taipei）。資料來源：現有 GitHub governance/v095 checkpoint、Actions runs，以及已列出的 Google Drive 對象；僅記錄已觀察的證據，不自動提升生產資料。

## 正式判定
- Bronze：v0.93 已觀測原件遷至 v0.95 共 41 個目標檔（2026-11-05 收據），但來源全集、TDCC 原生 HTML 證據、全檔 readback SHA 和其他來源分類未完整驗收；全月 release **BLOCKED**。
- Silver：已有若干真正型別化的來源資料集和 QA 輸出，但並非全部正式 Silver；部分 Parquet 仍保留 native_row_json，不能當成完成轉換；全月 **INCOMPLETE**。
- Gold：最新 2026-11-06 checkpoint 記錄 9 個描述性輸出範圍、337,504 列（不同表可能重疊，不得當作獨立股票日數）；未完成全部 400+ 指標，也未通過歷史 PIT；正式全月 **INCOMPLETE**。
- Gate：僅各來源/資料集 >=98% 下載與內容正確，且原件完整、身份日期單位、無前視偏差之關鍵缺陷隔離後，才能放行。不可用檔案存在或 workflow success 代替正式驗收。

## 本次核對的證據
- governance/v095/202609_BRONZE_MIGRATION_RESUME_20261105.json
- governance/v095/202609_BRONZE_GATE_STATUS_20261105.json
- governance/v095/202609_SILVER_FINALIZATION_ACTUAL_RUNS_AND_GOLD_SCOPE_20261106.json
- governance/v095/202609_GOLD_LATEST_ACTUAL_OUTPUTS_AND_UNFINISHED_20261106.json
- governance/v095/202609_SEVEN_GROUP_PIT_GAP_CHECKPOINT_20261106.json
- governance/v095/CANONICAL_BRONZE_SILVER_GOLD_USER_DEFINITION_20261106.json
- governance/v095/PHASE1_FLAGS.json（BULK_COPY_APPROVED=false、RELEASE_APPROVED=false）
- Actions 42127149284 Phase 1 governance-readonly success；42129518119、42129905996 分項轉換 success；最新三個其他恢復工作 42130100238、42130621704、42131665618 failure，需分開診斷，不得把它們當作三層完成證據。

## 阻擋與下一步
1. 完成六來源的正式資料集全集和 v0.93→v0.95 逐個原件 Drive ID / SHA / 日期及失敗重試清單；保護 v0.93 唯讀及 v0.95 已正確檔案不重抓。
2. 釐清 TPEx OHLC 17,350/17,762 數值化（97.68%），412 非數字必須依官方不適用/停牌/其他欄位分類重計適用分母。
3. TDCC 來源原始 HTML 和公告時間；TAIFEX 非 Tick 16 類真實欄位/觀察日期/單位；NDC 5 sheets 觀察月份/版本；MOPS 季報與正式公告版本；TWSE/TPEx 籌碼/融資融券欄位與市場標的身份逐項對應。
4. 補齊前 60/120/240 交易日與多月營收等歷史 Silver 才能計算長週期 Gold，使用當日已公告資訊做 PIT。
5. 逐項核對 400+ 指標 definition → Silver dependency → computed Gold file/rows/QA/PIT；無資料的指標維持停用。

本報告為可稽核的第一階段檢查記錄；**不表示已觸發遷移排程、已搬動新資料、已通過 Bronze/Silver/Gold 生產放行**。
