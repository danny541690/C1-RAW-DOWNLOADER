# JARVIS C1 v0.95 — 終極版中央調度與三層資料庫規格 R1
日期：2026-11-06｜適用倉庫：danny541690/C1-RAW-DOWNLOADER｜資料庫：Google Drive/C1_0.95

## 一、目的、時序及硬性限制
唯一正式調度來源是 `config/v095_ultimate_r1.json`，配套 workflow 是 `.github/workflows/v095-ultimate-r1.yml`。所有舊 v0.93 自動 cron 應保持停用；保留舊版原始檔作為不可變來源。正式建庫方向從 2026 年最新官方已公布資料往 2000 年 1 月回補；**第一輪只允許 2026-11、2026-10、2026-09 小量 canary**。只有每層 QA、Gold 應計算指標、PIT、血緣和缺口例外均正式簽核，才准打開 2026-08→2000 的回補；在此之前不得越過 2026-09。這個 gate 是資料證據條件，不是 GitHub 執行成功。

## 二、調度器、佇列及並行
- 中央調度器 1 個，GitHub Actions schedule `*/15 * * * *` UTC、手動 dispatch；GitHub 的 cron 是盡力觸發，不能承諾準時或永久執行。
- 14 個「可分配工作槽」，不是 14 條獨立 cron：Bronze 6（TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC）、Silver 4（PRICE_VOLUME、FUNDAMENTALS_FLOWS、TDCC_OWNERSHIP、DERIVATIVES_MACRO）、Gold 4（TECHNICAL、CHIP_OWNERSHIP、FINANCIAL_VALUATION、CROSS_ASSET）。
- 正式起始全域 active<=6，同時間可逐級測 10→14；不能因空槽而製造沒資料的工作，限制 Drive request 及限制來源同時下載數；TDCC 可切週、股票範圍分片，各分片唯一寫入者。
- 同一 Task ID = (version, source, dataset, month, shard, transform_version, input_sha)，狀態機 PENDING→LEASED→RUNNING→QA→PASS；出錯轉 RETRY_AT 或 BLOCKED、QUARANTINED。最多 3 次暫時性重試，遵守 Retry-After；與 schema／無資料／公式未定義等永久性錯誤分開。15 分鐘巡檢需先查 GitHub run 是否活著、租約是否逾期，不能直接重派同一分片。
- Manifest、Checkpoints、Error Register、Retry Ledger、PIT Ledger、Indicator Registry、Lineage Index 和 Acceptance Ledger 必須持久化並帶版本／來源雜湊。唯中央調度器合併任務狀態；worker 寫不可變分片結果而不是搶寫同一 JSON。

## 三、Bronze：v0.93→官方→FinMind
1. 按來源+日期尋找 v0.93 已存在原件，驗證檔名／大小／SHA 後只複製缺失，保持舊來源不可變。
2. 對確實缺失的 dataset/date 才依序查 TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC 官方原件；官方不存在或有效可得日期以前的資料標記 NOT_AVAILABLE，不可無限重試。
3. 僅在相容且官方確實無法補齊時，以 FinMind 免費端補缺，保留兩邊不同口徑標籤。排除 tick／分鐘級非需求資料。
4. Bronze 保存原始 bytes、下載時間、文件所屬日期、公告日期（若官方提供）、官方 URL、版本及 SHA-256。正確原件不得重新下載或覆寫。

## 四、Silver：標準 Parquet
- 依資料集合約轉成標準 Parquet；保留欄位對照及原始數值，統一日期 Asia/Taipei、股票 TSE/OTC 代碼、金額 億元、量的股／張口徑、交易場別、主鍵唯一性、NULL 原因和欄位型別。
- 禁止 OHLC 推估、零成交價自動補零、把盤後資料填入不相容時段，或將當天下載資料當成當時已公開。
- 每份 Silver 保留 Bronze SHA、原始壓縮檔 member、轉換器版本和 QC 結果。興櫃 Bronze 保存但不進入 Gold 分析母體。

## 五、Gold：443 指標和公式 DAG
- 每個 ID 記錄 formula_id、formula_version、dependencies、data_interval、warmup、PIT availability、input Silver 檔案／SHA、output Gold 路徑、精確性標記。
- 依四工作池運算，能算的先算；歷史暖機不足（MA60/120/240、TTM、24 月新高）標記 NOT_APPLICABLE_HISTORY；缺 XQ 分點資料的項目標記 SOURCE_UNAVAILABLE，不以 0 代替。
- 非依賴未核准跨期數據的「單月描述」與「歷史回測」分開驗收；443 ID 名單存在不代表 443 項公式正確。

## 六、PIT、血緣與查詢
- PIT 必須追蹤 first_published_at、available_at、revision_at、source observed_at 和證券身分 asof；沒有正式公布時間證據不准用於歷史回測。九月營收在十月公布，不得視作九月30日已知。
- 指標／日期／股票反查：Gold formula+value→ Silver source hash+row→Bronze raw URL/file id/member+SHA。回查應有 forward/reverse index，缺證據時明確返回 BLOCKED 而不假裝可查。
- ChatGPT 查詢入口應有可直接呼叫的服務或 GitHub workflow_dispatch query 模式；GitHub 不能當毫秒級常駐資料庫。
- 任務完成定義：來源分片的 Bronze、Silver、Gold（適用者）、PIT（歷史用者）、反向血緣都通過；個別不適用與官方未存在可被文件化，不能計失敗。

## 七、第一輪 2026-11→2026-09 小量驗收
- 先做 Drive 八根目錄、六來源 3 個月份、443 指標名單、九月既有 Silver/Gold 核對；保留全部既有 2026-09 已驗證檔案。
- 2026-11、2026-10 若無 v0.95 原始分區，先標成 WAITING_V093_OR_OFFICIAL，不能憑舊 v0.93 的排程執行日當成 v0.95 已下載。
- 每輪只讀取少量 metadata+必要 QA，遇擋點只對該分片排入後續工作，寫 Run ID、Manifest、Checkpoint 與缺口清冊。
- **若缺少可安全重用的 v0.93 原件與已核准來源契約，不准直接網路亂抓或宣布通過**；先報來源缺口與發行阻擋。
- 試點通過後在同一中央調度器切換歷史回補模式，依月 2026-08→2000-01 逐月往前；最新日增量更新佇列永遠獨立保留。

## 八、不可妥協的安全閘門與驗收證據
- 不因 GitHub Actions exit 0 視為資料庫 PASS。不重抓已驗證資料、不刪除 v0.93，不覆寫正式 Silver/Gold，任何有差異輸出用 versioned filename。
- 每輪記錄（已檢查、新完成、缺失、錯誤、跳過、待公布、待 PIT、已阻擋）與分來源日期覆蓋率。
- 發布條件須有清冊完整度、QA 百分比、443 ID 對照狀態、PIT、SHA 血緣 readback、可用查詢實測。
- GitHub repo 和 Google Drive 中各留同版 spec／config，且必須實際讀回確認。GitHub cron 若漏觸發由下次持久化 checkpoint 繼續。

## 九、既有成果與仍未閉合的範圍
截至本規格建立前，v0.95 正式 Bronze 資料樹僅觀察到 2026-09 六官方來源分區；九月已有上市 21,803、上櫃 17,350、月營收 1,980 的部分 Gold，TDCC Silver 276,097 列。443 ID 的公式對照、歷史 PIT 和各來源總契約仍未全面驗證。以本規格執行 pilot 必須重用成果而非宣稱完成。

## 十、交付與停止條件
建立新 `v095-ultimate-r1.yml`，不復活任何舊 cron；完成一次 2026-11~09 小量真實 Drive 診斷；同名版本文件存 GitHub 與 Drive。從 2026-08 往 2000 自動拓展的開關只有 pilot 的全證據 gate 能開啟；出錯時系統停止的是特定分片，不是整個隊列。
