# JARVIS v0.95｜2026-09 Bronze–Silver–Gold 三層生產化 R2

日期：2026-11-06；狀態：分層上線、全量 PIT/443 指標 NOT CERTIFIED。此文件是流程契約，不代表九月 100% 完成。

## 一、已核實基線（真實來源）
- GitHub 來源盤點 run 42145176095：遷移清冊 41 個檔案，v0.95 名稱與大小 41/41 一致；六來源觀測 244,962,801 bytes；39 個候選 dataset contract 未簽核。此比率不是所有來源、全市場數值或 SHA 的完整度。
- v0.93 原始 → v0.95 Bronze：TWSE 3 個主要檔、TPEx 7 個主要加官方補件、MOPS 7 個、TDCC 每週分片及原件保留、TAIFEX 19 個非 tick、NDC 1 個官方 workbook。TDCC 10,949 原件的存在證據不能與 v0.95 全量複製視為同義。
- 指標 443 ID 由 v0.93 原主控對照報告整理、推送至 v0.95 governance：run 42145491402，並非 443 項已完成計算。57 項主力/分點直接依賴 XQ，無來源時維持 unavailable。
- v0.95 September autopilot state：Bronze 子工作 PASS 但 source contract universe 未簽核；Silver 部分完成且 TDCC 曾發生 Drive BrokenPipeError；PIT = false；Gold 已有局部 descriptive candidate。
- 現有 Gold FEATURE_STORE、APPROVED_VIEWS、PIT_SNAPSHOTS 沒有 443 項正式釋出證據。

## 二、唯一來源先後順序、缺失安全
同一 dataset/date/security 欄位只能依序:
1. **0.93 原件**：只讀查詢，依來源 ID/SHA 及月份找出原件；先複製 immutable bytes 至 v0.95 Bronze，再校驗 SHA256/大小/內容日期/來源單位/有效證券身分。不覆蓋已 PASS 原件；失敗隔離。
2. **六官方（TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC）**：只針對第 1 層已對帳確認 missing/corrupt/schema mismatch 的確切資料單元執行最多 3 次下載，來源網站與資料契約一致才採用；空回應要辨識「非交易日、未發布、官方不提供、暫時故障」。
3. **FinMind 免費版**：只有第 2 層的官方來源 unavailable 或 confirmed missing 且 FinMind 提供可相容 dataset/date/調整口徑的情況才補；保留 origin=FinMind_Free，不能無聲替代官方或反向覆寫官方已核驗資料；遇 rate limit/backoff 留斷點。付費 Backer 來源與 Free 物理分開。
來源差異需放在 provenance/missing_reason/quality_status，不得變成 0。上市上櫃分析、興櫃原始留存而不進選股 Gold。只保存日 K 以上，排除 tick、分鐘、逐分點明細（需要時指標先停用）。

## 三、三層資料 Schema 與依賴圖
Bronze immutable 原件（SHA256、source_file_id、source_dataset_id、source_revision、trade_date、observed_at、official_published_at、capture_at、origin_version、license_tier、receipt_id）。按 source/year/month/dataset 保存，檔案 checksum 永不覆寫。
Silver 以日/週/月/季的正確 grain 轉 Parquet：security_id、market TSE/OTC、security_type、effective identity interval、date、value、native_unit、unit_standard、source_receipt、source_sha256、published_at、available_at、PIT_eligible、quality_status、null_reason、schema_version。金額單位統一億元，價格 NT$/股，成交量依 native 及明確轉換，不混張/股；月營收期別與公告日分開，季報累計/單季分開，TDCC 週資料不可假裝成每日當日可用。
Gold 443 指標：indicator_id -> formula_version -> dependency_dataset_columns[] -> dependency_asof -> rolling_warmup -> QA/PIT -> [value nullable + missing_reason]。對市場/類股/證券做發布日 as-of join；技術 240 天、RS 240天、TTM EPS、月營收 YoY 等必需提早抓 warmup；無法回溯時 PARTIAL/UNAVAILABLE，不能用今天的類股/身分或修訂資料倒填九月。
零件與關係由六個資料表或檔案實作：SOURCE_DATASET_CONTRACT、RAW_RECEIPT_MANIFEST、SILVER_FIELD_CATALOG、INDICATOR_DEPENDENCIES_443、PIT_AVAILABILITY_INDEX、FEATURE_PARTITION_MANIFEST。第七個 TASK_LEDGER/REPAIR_LEDGER 負責執行斷點；不新增使用者可見的第四資料層。

## 四、建議工作調度（不是 16 條獨立常駐 cron）
**唯一總控**：15 分鐘 checkpoint/supervisor；GitHub Actions workflow_dispatch 進入；每 source/dataset/month/partition 綁定唯一 lease，結束保存 checkpoint；每輪 1 次超時回收；續跑只執行 FAILED/WAITING/STALE，不重跑 VERIFIED。
**Bronze 4 個並行來源池**：
B1 TWSE+TPEx（source-native API 有速限，池內各來源最多 1 active）；B2 MOPS+NDC（低量），B3 TAIFEX（CSV 大檔 19 筆非 tick） B4 TDCC（10,949 原件/184 bundles 高 metadata 成本，以批次 ZIP/批次 SHA 避免逐檔重抓）。每池依 0.93→六官方→FinMind Free 的順序，官方各來源每批總併發保守 1-2，不因總控多開就向同站同時轟炸。
**Silver 5 個計算池**：S1 TSE/OTC OHLCV；S2 法人/外資/融資/融券/股本；S3 MOPS 月營收+季報；S4 TAIFEX+NDC；S5 TDCC 週資料（獨立避免 BrokenPipe 造成其他池停擺）。平行 3-4 池、TDCC 獨立 1；從原始 SHA 有變更的 partition 才重新運算。逐池 output 需要驗證行數、主鍵唯一、單位、型別及 QA。
**Gold 4 個計算池**：G1 技術/量價/RS、G2 籌碼/所有權、G3 營收財報/估值、G4 類股大盤/跨資產/決策品質。高負載 G1/G2 可各拆兩 shards，G3/G4 各一，總同步 worker 最高 4–6，依 GitHub 分鐘數、Drive API quota 和 run logs 調整。指標按依賴 DAG；只重算受影響日期/證券及 rolling 窗口，跨月 warmup。
**QA 2 個隔離檢查池**：Q1 來源/Schema/跨日/跨來源內容與母體；Q2 公告時間、日期有效身分、公司行動、look-ahead、443 指標依賴及回測 PIT。不同池報告不互相掩蓋 FAIL。

## 五、PIT 與正式讀取
PIT 的關鍵欄位：event_date, report_period, first_publication_at, available_at, revision_at, snapshot_asof, execution_after_close。不能把 2026-11-06 才取得或更正的財報數值當 2026-09 當時已知資料；缺 publication evidence 列 PIT_BLOCKED。
AI 查詢採用固定 JSON 索引 manifest -> Parquet feature partitions（範圍查詢以 DuckDB/Arrow 服務批次查詢；ChatGPT/Gemini 呼叫 GitHub/Jupyter 臨時 query runner 取得 compact JSON 結果和依據）。聊天模型不直接掃 245 MB Bronze。每次回傳 request_id, asof, universe, indicator_ids, values, null_reason, PIT, source ids, QA version, updated_at。未來 Google/ChatGPT 需具可控執行器，僅靠 Drive 檔案不等於即時查詢 API。
**發布門檻**：候選能用於「目前描述性」分析不等於回測可用。只有各 dataset 資料 QA PASS+所需指標公式核准+PIT PASS 才發布該指標分區至 FEATURE_STORE / APPROVED_VIEWS；未通過不發布該指標，但其他獨立指標可繼續使用。

## 六、阻塞分級與排程閉環
- DATA_GAP: MISSING -> v0.93 lookup -> official retry(<=3) -> FinMind eligible gapfill -> NULL/UNAVAILABLE
- FORMAT: quarantined -> Silver parser correction -> deterministic rerun affected partition
- TEMPORARY: 429 / BrokenPipe / 5xx -> exponential backoff + jitter, resumable session, same SHA idempotence
- PIT: missing first-publication evidence -> PIT_BLOCKED (cannot bypass to backtest)
- DEFINITION: missing formula/ambiguous XQ methodology -> FEATURE_DISABLED (not 0 or false PASS)
- NEVER: delete Bronze; take current-as-of valuation and backfill past as historical fact; label job SUCCESS as QA pass; let one missing TDCC partition block independent OHLCV/finance calculations.

## 七、對九月進度的實際結論
- 已有 v0.93 to v0.95 41/41 observed size/name receipt；離全市場完整與 39 個簽核 source contract 還有距離。
- 443 個 ID 已建候選目錄；443 個 Gold 數值與 PIT 仍未完成。原 0.93 audit 的 57 直接依賴 XQ 主力/分點項目因官方/FinMind 不一定等價而應停用。
- 2026-09 完整生產驗收尚不得標記 COMPLETE；僅可對通過的 subset 做 descriptive analysis。
- 執行策略先維持現有 Run #42142708197 的銀層續跑，補一個 source-priority 實體查核（Run #42145176095 已成功）並建立 Gold 443 ID 參照目錄（Run #42145491402 已成功），避免再從零建同一月份的已驗證檔案。
