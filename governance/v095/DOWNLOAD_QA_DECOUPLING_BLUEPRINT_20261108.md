# JARVIS v0.95 | 2026 Download / QA / Repair / Silver / Gold Decomposition Proposal
日期：2026-11-08。**狀態：設計案／不自動停用既有工作；未測試通過不可切正式排程。**

## 現有 GitHub 事實與根因
- 六大來源常態作業：TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC；前兩條每 15 分鐘、後四條每 30 分鐘。來源獨立但來源內同一 GitHub Job 串連下載＋Silver／Gold（必要時讀回與血緣）。
- TWSE Run #42466997074 約 79 秒；MOPS #42462994379 約 61 秒；TDCC #42462994307 約 639 秒；TAIFEX #42462994228 約 156 秒；NDC #42462994213 約 25 秒。這是 CI 工作總耗時，並非精確單階段耗時，不能拿來直接聲稱新架構加速多少倍。
- TWSE／TPEx 每批 10 個平日候選；MOPS／TDCC／TAIFEX 來源封存每批 3 份，且重複掃描 Drive 管理目錄；TDCC 來源 + 轉換一條 Job 最慢。
- TAIFEX 官方報表類型混雜，29 份不符目前 spread-order adapter 的候選已被 3 次格式驗證後隔離；屬資料集類型／解析器不一致，不能以相同方式重抓三次解決。
- NDC 單一官方歷史 ZIP 已驗證 321 觀察月份；不應每輪下載 321 個月，Silver 可用已驗證 ZIP 增量轉換。
- 日期表 2026/11/08：現貨官方交易日 205 天；TWSE/TPEx 巡檢游標 186/222 平日＝83.8%；各層 177/205 個官方交易日有候選檔＝86.3%。候選檔存在 ≠ 全來源正式驗證完成、400+ Gold 完成或 PIT。

## 參考的官方工程設計與來源
- Microsoft Fabric Medallion: https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture
- Azure Databricks Bronze/Silver/Gold: https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion
- Microsoft ADF watermark incremental pattern: https://learn.microsoft.com/en-us/fabric/data-factory/tutorial-incremental-copy-data-warehouse-lakehouse
- Microsoft ADF copy resumability: https://learn.microsoft.com/en-us/azure/data-factory/copy-activity-overview
- GitHub concurrency groups: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- GitHub Actions job limits: https://docs.github.com/en/actions/reference/limits
- Google Drive quotas / backoff: https://developers.google.com/workspace/drive/api/guides/limits

## 建議 18 條邏輯工作（預設同時在跑上限 8，視實測擴到 10–12）
- D01–D06：6 個來源專用 Fast Download；只做來源回應確認（URL/HTTP/內容大小/所請求日期/原始 SHA，保留原生 bytes），封存 Bronze、寫 Manifest / durable cursor，資料型式錯誤記錄但不進深度解析。**單一問題不得卡住別的日期/來源**。
- Q01–Q04：4 個獨立 QA 工人池（現貨 2 來源分區、MOPS 財報營收、TDCC 週資料、TAIFEX/NDC 按資料集切分，後兩種採不同 adapter），不與來源下載工作共用時限；驗原生欄位/日期/數值/單位/重複/發布資訊，產出 ALLOW_SILVER、QUARANTINE、NEEDS_REPAIR。
- R01–R02：2 個修補工作，R01 處理暫時性 HTTP/授權/429/5xx/缺原檔（有界 3 次，backoff + jitter）；R02 處理 parser/schema/欄位版本與 PIT 缺失（永久錯誤一次隔離、等 adapter 版本變更再驗證；不重複網路請求）。
- S01–S02：2 個 Silver worker（市場日資料／非日資料），從通過 QA 的新增單元立刻轉型、去重，金額換算億元，保留來源原始單位及 null 來源。
- G01–G02：2 個 Gold worker（技術+籌碼；財報+總經），只計依賴資料具備的可用指標；未具備 400+ 指標的依賴先列 Missing Indicator Ledger，`enabled=false`，不得填 0。
- L01：1 個雙向血緣稽核（Bronze↔Silver↔Gold、Drive SHA readback、PIT、依賴圖及欄位映射）。
- C01：1 個 Manifest/Checkpoint/Run Ledger 統一管理＋進度報告。**來源下載和下游 QA 可以同時進行；只在同一資料分區設寫入鎖。**
總計 D6 + Q4 + R2 + S2 + G2 + L1 + C1 = 18 條邏輯 Job，並非要 18 個永續佔住 runner；分批／事件觸發完成即退出。

## 一筆資料狀態機（缺陷回圈不阻塞同批）
`DISCOVERED→RAW_SAVED→RAW_SHA_VERIFIED→QA_PASS→SILVER_WRITTEN→GOLD_PARTIAL_OR_DONE→LINEAGE_PASS`.
側支：`RETRYABLE`（只重試 429/5xx/網路暫失、最多 3 次）／`QUARANTINED`（schema/zip/日期不符），`NULL_AFTER_3`（只對該候選單元，保留錯誤證據）；`PIT_PENDING`（描述性資料保留但不能進歷史回測）。
Gold 的 Stage 3→4、24 月高、TTM 等依賴 N 個月/季的指標，建立 dependency watermark；只有完整 lookback 且有 PIT 的單元才標為「回測可用」。新來源修補時只重算受影響日期與指標。

## 增量 / 雙向核對與重試
- 來源唯一鍵：`source + dataset_id + trade_date/report_month/snapshot_date + version + request_parameters`；原始檔 SHA 不變不得重抓，Drive 目錄 listing 請用一次索引/緩存批次讀取，不在每檔每層全目錄反覆 list。
- 每次上傳先存 raw，再透過 SHA readback 綁定 manifest；在 Manifest 存 `bronze_id,bronze_sha,source_date`。下游以 `dataset_id + source_sha + adapter_version` 做冪等鍵。
- 多線與原本 6 條分開時，***不可讓原 Job 和新 Job 對同一分區雙寫***。GitHub `concurrency` 的工作群組以來源／年份／月份或分區 ID 分隔，checkpoint 只讓一個提交者做原子狀態轉移。
- GitHub concurrency 同群最多一個正在執行＋一個 pending；新 pending 可能取代舊 pending，故重要工作不要以同群排隊作唯一永久佇列；永久任務存 Google Drive Manifest。
- 未知歷史來源 / 尚未建立的週資料 / 官方無交易日不能用自然日當必須完成的分母；完整率至少分「已抓 raw／已 QA／已 Silver／已 Gold／PIT 可回測」五欄，且以契約和來源可得日期算。
- 下載及 QA 雙工池獨立記錄 CPU 秒、Drive API request、429、重試、轉換秒數、run 中產生的有效日期與檔數、sourced bytes/sec、成功/失敗率及成本，避免只比總 job 次數。

## 分段切換，不直接停止原本排程
A. 先做 2026-09～2026-11 已知有來源原始檔的對照批次，shadow-read 舊 Bronze，不重抓；新 QA 和 S/G 產出到新候選分區；比對兩邊 SHA/列數/來源日。
B. 使用 2026-01～最新增量隊列，在不與舊寫入者重疊的分區做 D01–D06 獨立快抓，並行 Q/R/S/G。
C. 實測 3 回合：完整通過日期與 schema、雙向血緣、PIT 限制無回退，且新方案吞吐量及 Drive 429 不差於舊方案，才關閉舊下載+轉換聯合作業的 cron，逐來源換成新方案。
D. 2026 年達可解釋的分母與驗收狀態後，再將 manifest/retry/source-capability 規則擴展至 2000–2026 歷史批次；原始來源早期不存在的日期列 `NOT_APPLICABLE`。
