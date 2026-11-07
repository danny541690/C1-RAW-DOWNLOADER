# JARVIS v0.95 R9｜正式全量下載規格與 GitHub 執行狀態核對（2026-11-07）
單一執行庫：`danny541690/C1-RAW-DOWNLOADER`；結論：**v0.95 資料模型／治理規格足以作為唯一正式規格；毋須重新移植 v0.93 完整核心；尚未有證據表示全量正式下載流水線已開通。**

## 1. 權威來源與時點
- Google Drive `JARVIS_C1_v0.95_Architecture_Management_R1.xlsx`（2026-11-04；ID `1zR1FkurqbpsWMl9y71PdDlzGHqIqz8oU`）：15 個表段，八大分層（00治理／10 Staging／20 Bronze／30 Silver／40 Gold／50 Research／60 OperationsQA／70 ReleaseBackup）、六官方＋FinMind Free／Backer、16 調度槽、完整狀態機及 G0–G5；其中 v0.95 migration/production 欄位多數當時標 NOT_STARTED/NOT_DEPLOYED。**這是設計凍結版，不是 2026-11-07 最新線上實測狀態。**
- Google Drive `JARVIS_統一問題總帳_20261102_R1.xlsx`（ID `1C5yWlF_UBZadAOPYAmD3PNAyh7nCkCQJ`）：89 筆問題索引，4560+ 憑證／歷史列；「問題索引」不等於 89 個目前損壞的資料分區。其多項 v0.93 核心問題已修本機/單元測試，但原表註明範圍修復≠全面資料閉環，例如 RAW-I07 189,521 任務分頁測試、RAW-I06 TDCC 49.5MB 原件 SHA、RAW-I22 1602 個空來源回覆、RAW-I12 來源 adapter 綁定未完成。不能直接視為今日正式 v0.95 已發布。
- 最新 GitHub 實證：R6 `42356953109`，R7 `42358883518`／`42358660576`、R22 來源測試 `42359498188`、全史發現 `42358968057`。正確已證據化的候選資料禁止無理由重抓；候選 PASS 不等於 PIT PASS。
- `governance/v095/PHASE1_FLAGS.json` 現值：`BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`、`last_evidence_verified=false`。

## 2. 16 槽、14 槽與真正定期排程不是同一回事
|概念|實際功能|狀態|
|---|---|---|
|v0.95 正式來源規格 16 槽|六官方×雙向=12；FinMind 免費／Backer=2；DAILY=1；REPAIR=1。**邏輯任務類別**，同來源單一 writer。|設計表已建立；未完成 16 類全量正式執行驗收|
|ULTIMATE R1 14 Worker|Bronze6／Silver4／Gold4，用於候選檔案/收據檢查，不是等同 16 個官方抓取程序。|R1 自動 Cron 已關、保留手動；先前 14 收據成功≠全史抓取|
|R6 Controller|每30分鐘 cron `7,37 * * * *` (UTC) 進行輕量歷史清冊、安全閘門。手動 full 才進行全部候選讀回和轉換。|已部署，沒有從 2000 開始下載|
|R7 delta-only|每2小時 cron `17 */2 * * *` (UTC)，核對六類待處理問題／跳過 12 個 scoped-candidate 驗收憑證。定時模式不重新叫 TWSE probe。|已部署，`download_count=0`、`existing_files_rechecked=0`，沒有正式缺件寫入|
|其他 v0.95 workflows|本次逐項檢查 52 條 v0.95 工作流最前部觸發器，只有 R6/R7 含 Cron；其他多是 push／dispatch。|不等於所有 legacy v0.93 或私庫排程全部已關，需另外清查|
|Phase1 governance|僅 schema 和治理檢查；push/dispatch。|success 是 CI 驗證，不是資料發布|
## 3. 2000–2026 全量下載要求（v0.95 唯一規格）
- 2000-01 至當下已正式發布日期，2026-11/07 尚不是完整 11 月；來源可得日決定 expected 分母。TSE／OTC 分析，興櫃保存但不供主要選股；不包含分鐘／小時頻率。原生資料／調整價分開，金額研究顯示 `億元`。
- 來源先序：TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC 官方；FinMind Free 補缺；FinMind Backer 只有使用者購買且權限驗證後才啟用。不能把 FinMind 擷取與官方實際可得等量視之。
- 雙向掃描同一個 task ID／source lease；任務鍵須納入 dataset、market、觀測期間、來源版和解析契約；來源有歷史深度差異不算自動缺件。據官方文件：TDCC 週持股資料集建自 2008-07 前 102 dataset-month 標 outside-this-series；TPEx 2003-08 前 43 月現行 bulk 不支援，需尋找不同 legacy 路由。
- Task 狀態依 v0.95 表：EXPECTED/PENDING/FETCHED_UNVERIFIED/VALIDATED/PIT_APPROVED/NOT_YET_PUBLISHED/NOT_AVAILABLE/NOT_APPLICABLE/DOWNLOAD_ERROR/CORRUPTED/SCHEMA_ERROR/VALUE_ERROR/PIT_ERROR/REPAIRING/BLOCKED/CLOSED_VERIFIED；要由生產 Worker 按實際來源證據推進，而非事先對 2261 discovery 月份假設準備成功。
- Bronze：官方原始 bytes 不可變、來源 URL＋日期＋版本＋SHA256＋fetched_at、合法下載／適用分母、不重覆下載、Drive 讀回與持久 checkpoint；Silver：標準化 Parquet 及 schema/主鍵/日期/交易狀態/原生單位；Gold：443 個真公式、發布 available_at、版本與暖機、歷史 as-of、雙向血緣；沒有上游證據的指標停用。
- G0 transport、G1 schema、G2 semantics、G3 PIT、G4 research、G5 production release。**安全 Bronze 原始收集不應因 Gold 443 公式未完成而全數不動**，但正式 v0.95 Bronze writer 的來源契約／不覆寫／Crash Recovery、CAS 單寫者是第一個必驗門檻。

## 4. v0.93 是否必須移植？
**不必移植整套 v0.93，也不應再搬一份舊資料庫。** 同庫的 v0.95 已有 `v095_202609_autopilot.py`、`v095_202609_R3_scheduler.py`（GitHub runtime checkpoint）、`v095_202609_unified_resume.py`（已知檔案重用）、`v095_release_maturity.py`（PIT/覆蓋率門檻）、R6/R7；舊 `v093_source_git_store.py`、`v093_source_coordination.py` 具有已測試的 Git CAS、lease、fence，可**只作互通測試/邏輯參考**。必要的是 v0.95 生產 task writer 以真實 Drive 物件與雙 Runner 競爭測試證明「相同契約」已達成，而不是檔案一定命名 v093 或複製它。
## 5. 對照問題總帳，未解除不等於無法先做 Bronze
- 9 月 TPEx 非數值 412（255 有成交量、157 零）應保留 native `---`、分離普通股票 master，不能填 0 或認定股票不存在。
- TDCC R22 2026/10/30 共有 4,111 個 group，496 警示（58 share 差異、451 percent），應保留全部週別原始、按官方集保庫存分母核對；不等於整個 9 月失敗。
- R22 TWSE 原端點最近 Run `42359498188` 成功；先前 timeout 原因已定位與有界重試改善，不能用單次 PASS 推斷 27 年所有來源可靠。
- 2000–2026 的 2261 dataset-month **僅屬 discovery 清冊**，已核實正式 expected/download-ready 仍 0；上線全量的實作必須依實際已發布／可得來源建立 READY／NOT_APPLICABLE／BLOCK 分流。
- 443 catalog 正反向候選映射 ≠ 443 完整公式與 PIT；可先收 Bronze，再增量完成 Silver/Gold 以避免雙重等待。

## 6. 建議唯一後續上線方案（採納現有 v0.95 表格，不新增架構）
1. 以 Google Drive v0.95 架構表作**規格主檔**，搭配 GitHub 最新 R8/R9、Run IDs、89 索引的 issue ID 更新狀態，不以 11/04 `NOT_DEPLOYED` 直接覆蓋後來成功的候選驗證。
2. 選一個已證實缺件且官方適用的 source×dataset×month，啟用 v0.95 **Bronze-only 小量真實寫入**：檢查 SHA+URL+時間、已成功先 skip、真正缺件才 GET／save、再 readback、Checkpoint、兩 Runner stale-owner 拒寫，失敗留 quarantine。此測試不得假裝所有 Gold 已認證。
3. 經以上通過後，僅先放行 Bronze 可用的有證據工作（初期 2–3 source workers，同來源單寫、兩端往中間掃描；觀察限流再提升 6/8）。所有 Silver/Gold PIT/Research Release 保留獨立 QA 閘門。
4. 不再啟動新 14 槽候選檢查作為全史下載代理；R6/R7 仍只作輕量與問題巡檢，新增 READY dispatch 必須沿用 v0.95 16 槽及單一來源鎖。未核實前 `BULK_COPY_APPROVED=false` 保持原狀。
5. 每一次成功交付確切 `run_id`、`downloaded/skipped/fixed/quarantined`、source URL、Drive file ID、SHA 讀回、Checkpoint ID、可用與 PIT 狀態，才能客觀宣告已開始實際全史下載。
## 核對結論
**v0.95 規格充分、歷史錯誤清單豐富，無須重做架構或回收/覆寫舊版資料；尚缺正式版 Bronze Writer 和持久任務執行的端到端上線憑證，不是再補一份 v0.93 設計說明就可以處理的問題。** 此報告只核對與留存現況，未修改原有生產旗標或自動開啟 27 年下載。
