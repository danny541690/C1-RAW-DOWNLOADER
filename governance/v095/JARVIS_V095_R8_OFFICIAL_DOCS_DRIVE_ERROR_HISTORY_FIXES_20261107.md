# JARVIS C1 v0.95 — R8 官方文件與 Google Drive 錯誤履歷逐項重查、程式修復、整合預驗收（2026-11-07）
唯一 GitHub 執行庫：`danny541690/C1-RAW-DOWNLOADER`。正式 `BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false` **仍不可解除**；本報告須區分已修程式、候選資料品質、真正 2000–2026 上線。
## 已檢查的私人 Drive 管理紀錄
1. `JARVIS_C1_v0.95_2000-2026三層遷移調度與驗收總方案_20261107`，Doc ID `1p2UHHa-evc7eChuAVQ-KD1E7mTlkHQpMb3mGmsQ4oyI`：只重抓缺件；由官方上市/公告時點計算 PIT；原始不覆寫；SHA、程式版本與 Market as-of；Gold 無公式關閉。
2. `JARVIS v0.95 R5 歷史錯誤履歷解析`，Doc ID `1qxfIwkl_CY4vV8FgHdVV_pp78k5prmDOdQLPIGI1TIU`：TPEx 412、TDCC 58/451、R22 TWSE 偶發 Timeout、未實作持久 v0.95 CAS。
3. `JARVIS v0.95 R7 9-11 月 Problem Only`，Doc ID `1Phq0DvBn6N1zXoskGK_shiFchTLL3NEXIgQHG7Zy_sA`：原先 12 candidate scope、六類待解；但必須補記每筆真實 SHA scope 與原始證據 Run。
## 官方文件根因與已修改政策
- 櫃買中心官方上櫃行情頁面：https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html ，現行 bulk 歷史資料自 2003-08，有不同年份查詢頁面。對 2000-01～2003-07 的 43 個 TPEX_DAILY_MARKET 月份需標 **LEGACY_TPEX_FORMAT_DISCOVERY_REQUIRED**；不能把「此新版 bulk dataset 無檔」當做「TPEx 所有歷史都不存在」或源下載失敗。原 repo `IndividualDailyInfo` 的 1994 起點仍未取得正式 live+PIT 證據。
- TDCC 官方：https://s.tdcc.com.tw/portal/zh/smWeb/qryStock ：集保股權分散表資料自 2008-07 建置，歷史查詢檔案在頁面公布一年的保存限制；資料是每週最後營業日結束後存摺餘額，ID 歸戶，百分比是**佔集保庫存比例**而非公司全部發行股數。對 2000-01～2008-06 的 102 個 `TDCC_WEEKLY_OWNERSHIP` 月份標 `OUTSIDE_THIS_TDCC_HISTORICAL_SERIES`。該說法不等於從第三方永遠取得不到舊原始檔。
- TPEx 原始 OHLC 的 `---` 不視為數字零，也不可光靠成交量判定停牌；逐筆分類 255 筆有量、157 筆零量，須加歷史 security master 和交易方式來源證據。
- 明確區分 Bronze 原生 bytes 驗證、Silver 型別/單位/主鍵及 Gold 公式/PIT/逐行血緣；Bronze 合格不得直接推出 Gold PASS。
## 本輪 GitHub 已提交的具體修改
1. `config/v095_r8_official_source_semantics_20261107.json`：官方來源日期、分母、TPEx null、資料集PIT四級安全契約。
2. `scripts/v095_r8_official_semantic_gate.py` ＋ 5 項 `tests/test_v095_r8_official_semantic_gate.py`：拒絕錯誤的 TDCC 比例分母、TPEx 2000 起始錯誤、偽造OHLC零與發布開關；Run [42358660576](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42358660576) SUCCESS，5/5。
3. `governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json`：12 個以前的 candidate scope 的雜湊改由實際 R6 Run 42356953109 Artifact 13568171926 逐項對照，明確標 `BRONZE_SHA`／`SILVER_SHA`／`OFFICIAL_SNAPSHOT_SHA` 等，刪除模糊的 `source_sha` 欄位。R7 Planner 不再接受空或非64位 SHA、缺 Run ID／Artifact ID 的跳過清冊；這只代表**已有先前候選證據**，非本輪重新 SHA 遠端驗證、也非整個月 100%。
4. `scripts/v095_r5_full_history_discovery_queue.py`：323 月×七官方資料集仍有 2261 候選，增加官方起點例外：102 TDCC out-of-series、43 TPEx legacy format lookup。Run [42358968057](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42358968057) SUCCESS；`verified_expected_dataset_months=0`、`download_tasks_released=0`，沒有虛假全量上線。
5. 既有 R7 定時 Workflow 現在每兩小時做問題清冊；來源 TWSE 現場抽測僅 manual/push 重跑，**不再每輪都測已通過的 API**，也不重抓 12 candidate scope。Run [42358883518](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42358883518) SUCCESS。
6. **修復真正 R22 同一路徑來源 Timeout**：隔離分支 `test/jarvis-v095-parquet-isolated-20261104` 的 `tests/v095_r17_live_source_smoke.py`：僅針對原失敗 TWSE 同 URL 暫時性 Timeout/408/429/5xx 三次有界 retry，不重試 schema error、保留每次請求歷程；4 項測試。真正 [Run 42359141220](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42359141220) completed/success，TWSE 原端點 HTTP200、DATA_JSON PASS、R22 `TWSE=API_SAMPLE_PASS`。注意：這次一次請求成功，只可稱來源實測恢復，真實重試路徑以故障注入驗證。
7. **TDCC 58/451 逐組稽核**：R22 隔離分支新增 `r22_combined/TDCC_NATIVE_GROUP_WARNINGS.json`，其真實 [Run 42359260824](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42359260824) SUCCESS、4,111 groups、496 警示 groups，包含 58 share discrepancies、451 ratio warnings，源原始 SHA=`475c2765a60be8fd0c7d8be49cb924e7a4d2bf853c6850b0c308b19d5850cc6d`，可由官方欄位回溯每群；**全部來自 2026-10-30 snapshot**，不是 2026/09。當時原始代碼欄帶空白共長6，光用 `len(code)==4` 會錯；`strip()` 後有 422/496 為四碼格式、58 share group 中 39 個四碼格式，仍須歷史普通股身分驗證。新的 R22 程式只移除代碼外側空白，保留前導0和原生 Bronze byte；Run [42359498188](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42359498188) 是此修正後複驗，結論以完成日誌為準。比例多 99.90/99.91%，不能自動認定全是錯或全部由四捨五入造成；保留原始差異及未認證分母欄。
## 未通過正式歷史全量 Gate 的原因（不能跳過）
- R22 有限 source sample / TDCC R24 差異清冊不等於所有歷史 source contract。
- v0.95 真正多 Runner Drive Writer 的 CAS/Lease/Fencing/Crash Recovery 尚未整合驗證；只有 v0.93 核心回歸 PASS。
- 六官方來源 dataset×date×歷史證券集合 expected denominator 未完整核實；部分 MOPS、NDC 過去只是站台連通。
- 443 指標是 catalog/source-family candidate；公式完整 DAG、公告/修訂 available_at、暖機、每個 Gold row 正反向 SHA 均未認證。
- 先完成安全 Bronze 可用來源原始歸檔的分區級合約／不覆寫語意，再讓 Silver/Gold/PIT 各自依簽核 Gate 發布；不能改寫 `BULK_COPY_APPROVED=false` 來假裝全量已啟動。
## 此次驗收與工作狀態
- R8 官方文件／程式合約／歷史發現佇列／同源 R22 Retry／TDCC 詳細警告輸出已實際提交並驗證上述各 Run；其餘未完成事項仍列為明確未解，不得將「最新 GitHub Workflow SUCCESS」當作 27 年完整資料庫已驗收。
