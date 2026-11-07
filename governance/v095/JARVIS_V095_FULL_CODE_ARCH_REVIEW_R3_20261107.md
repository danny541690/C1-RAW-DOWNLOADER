# JARVIS v0.95 R3｜單庫系統與排程全程健檢、缺失修正及 2000–2026 上線路線
日期：2026-11-07　／　Repo：`danny541690/C1-RAW-DOWNLOADER`（目前 PUBLIC）　／　狀態：**PRELAUNCH / BULK BLOCKED**。
檢查對象：現行 ULTIMATE R1 Workflow、14 個工作槽、六官方來源與 FinMind 補缺邏輯、Drive OAuth／資料檔案、Checkpoint、R2 單庫方案、Bronze/Silver/Gold、443 指標、PIT、雙向血緣、2026-09～11 Pilot。
**本次已修改的內容：** 新增 `scripts/v095_r2_canary_gate.py`、5 項錯誤注入測試；ULTIMATE R1 新增「單筆失敗不得掩蓋」的最後驗收步驟與獨立 Artifact；R2 唯讀驗收增加 16 項架構健檢 `scripts/v095_r2_full_architecture_audit.py`。未修改原始市場資料、未打開全期回填。

## 1. 企業規範取其精華，不複製企業成本
參考 Microsoft Azure Architecture Center / Fabric：Medallion（原始不可變→標準化→可用資料產品）、Idempotent Consumer（重跑不重複副作用）、Bulkhead（來源/層別故障隔離）、Retry/Circuit Breaker（限額重試後停止擾動來源）及可觀測性。這些是**設計原則**，並不是 Microsoft 針對本專案做過驗證。
- [Microsoft Data Lake / Medallion](https://learn.microsoft.com/en-us/azure/architecture/data-guide/scenarios/data-lake)
- [Microsoft Fabric OneLake patterns](https://learn.microsoft.com/fabric/onelake/architecture-patterns)
- [Microsoft Idempotent Consumer](https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer)
- [Microsoft Bulkhead](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
- [Microsoft Retry](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)
**不建議**：為單一研究者架設 Kubernetes、Spark cluster、Kafka、Airflow、JupyterHub 常駐主機、企業資料目錄或多區域資料倉儲。當前使用 GitHub Actions＋Google Drive＋本機少量抽樣，最符合低維護成本；只有量測到瓶頸才額外購買服務。

## 2. 完整審查結果與問題分級
| 編號 | 等級 | 模組 | 發現 | 修正／驗收要求 |
|---|---|---|---|---|
| F01 | P0 | 執行真相 | 現有 14 Worker 多是候選證據查驗，不是 2000–2026 下載器 | 逐來源完成實際 download Adapter；每月確定 eligible、缺口、SHA、發布日 |
| F02 | P0 | 排程 | 單次 `push`、`schedule`、`workflow_dispatch` 執行不同步驟；手動十月重建不在 push 跑 | 路由單一 Controller 且按 READY 任務啟動，列出各 trigger 實際測試範圍 |
| F03 | P0 | 假成功 | 十一月 6 個來源日有 1 個 TWSE Timeout，舊版捕捉 rejected 但 Job 仍成功 | **已修**：新增獨立 Canary Gate，Rejected 或缺任一日期令 Pilot job 不可 PASS，保留 Artifact |
| F04 | P0 | Checkpoint | `save_bytes(... overwrite_if_changed=True)` 更新同名最新 checkpoint，缺跨 Runner CAS/fence | 正式回填前加入 Drive/GitHub 單一原子可見版本 pointer，需獨立測 race、stale fence |
| F05 | P0 | 來源重試 | 共用 `retry(fn)` 用於 GET/POST/UPDATE，發生「寫成功但回應丟失」時可能重建重覆檔 | 分拆 `retry_read` 和 `create_immutable_reconcile`，以 logical key + content SHA 去重，先查遠端再重試 |
| F06 | P1 | 效率 | 每15分鐘定時啟動14個 jobs（即使無 READY），每個 Worker 再裝 pyarrow 與 Google SDK | 1 Controller 每15分鐘查 READY、6 個處理槽起步，0 READY 則 0 Worker；依測量擴 8/10/14 |
| F07 | P1 | 雲端限流 | 14 槽各自連 Drive，config 2 req/s 只是欄位，尚無實際跨 Runner 協調限制 | 依來源設定個別 semaphore/rate budget，429 指數退避＋jitter，連續失敗 Circuit Breaker |
| F08 | P0 | Bronze | 來源資料「月份資料夾有檔」不等於所有適用資料集/股票/交易日都齊 | Dataset×市場×as-of 日期/發佈日生成官方 expected 分母，不能以 11/18 當覆蓋率 |
| F09 | P0 | Silver | 九月 TPEx 412 非數值（其中部分正成交量）仍待逐筆分類，簡單轉型會掉列 | 保留 native text、原始行索引、成交量、交易狀態與例外欄；重建數值可計算 eligibility |
| F10 | P0 | Gold | 443 ID + source-family hints 不等於 443 可驗證公式與 DAGS | 每項 formula digest、依賴鍵、最小暖機、發佈及修訂 as-of；不可計算時停用並寫原因 |
| F11 | P0 | PIT | 有 descriptive Gold 與 SHA 反向來源示例，但歷史 first_published_at / available_at 未全部驗證 | `available_at <= decision_asof`、知識截止時間、修訂版本及存活 universe as-of 全過才准回測 |
| F12 | P0 | 雙向血緣 | 443 候選正向映射＋5 資料集反向映射不足以涵蓋每個 Gold partition/row | 每一 Gold parent Silver SHA→Bronze SHA→官方 source+公告版本；反向檢驗所有下游；無孤兒/環 |
| F13 | P1 | Manifest | 既有 Drive 檔案可存取且回讀，但成功檔與錯誤檔無全史統一可復原管理帳 | 統一 partition manifest/leases/events/expected/source_lag/retry_after/fingerprint，所有狀態可重播 |
| F14 | P0 | 安全 | RAW 庫目前 Public，程式內存在某些非公開資源 ID 與組織研究細節，將私人模型合併會造成曝光 | 合併私人投資策略前改 Private；清查 Git history、Actions artifacts、過期憑證，Secrets 禁止寫入程式碼 |
| F15 | P1 | 維護 | 歷史上存在大量舊 Workflow（v0.93/v0.95），可能有手動或 cron 重叠 | 建立 authoritative workflow allowlist，對非權威排程設定 pause/disable，切換時避免同月重複寫 |
| F16 | P1 | 驗收 | GitHub Job success、Pilot data acceptance、公式 PIT release 常被混淆 | CI execution vs source/period acceptance vs certified feature vs production release 四個不同欄位 |
| F17 | P2 | 測試 | 需要跨流程真實故障演練，不只單元測試 | 3 次 fail→QUARANTINE、lease expiry、重覆 dispatch、Drive 回讀 mismatch、PIT 未到期、October/November 月跨界 |
| F18 | P2 | 資源 | GitHub Actions 頻繁安裝依賴與同步掃描 Drive 耗時/額度 | 精簡依賴、requirements lock、按需 jobs、分批 API、量測 requests/elapsed/bytes、按實際額度優化 |

## 3. 調整後最佳實作——「1 個 GitHub 庫，1 個調度器，不等於 1 個 Job」
- **唯一 repo**：C1-RAW-DOWNLOADER；若保留私人投資程式，正式整併前先 Private（切換可見性本輪未擅自修改）。
- **唯一執行入口**：現行 ULTIMATE R1 先保留測試，實作成熟後直接以 Controller R2 接手 Cron，不同時開兩套實際資料下載入口。
- **工作單元**：`source,dataset,market,observation_period,partition,schema_version,source_revision` 做穩定 task ID；同一 SHA 重用，不重新抓取。
- **狀態**：WAITING_NOT_DUE/READY/CLAIMED/BRONZE_QA/SILVER_QA/PIT/GOLD_QA/LINEAGE/RELEASED/RETRY_WAIT/QUARANTINED/NO_HISTORICAL_SOURCE，切勿以 SQL NULL 或 0 代表尚未發布。
- **初期並行**：6 個真正有 READY 的工作，其他 8 個邏輯責任槽可保留但不需佔用 Runner。穩定後才提升 8、10、14。
- **分區隔離**：Bronze 原始 bytes 不可變；Silver/Gold 內容由 upstream hash + formula digest + as-of 決定是否增量重算，最終最新資料 pointer 經單一 Writer CAS。
- **雙端回填**：近端最新資料優先供日常使用；2000-01 起最舊端掃官方可得性與資料缺口；兩端使用同一 Manifest、防重 ID。
- **六官方來源**：TWSE/TPEx/MOPS/TDCC/TAIFEX/NDC，FinMind 僅在官方不可取得且資料契約等價、使用條款允許時補缺；未適用/未到期不要假造缺檔。
- **三層 QA**：Bronze（真實來源 bytes、SHA、日期、完整性）；Silver（Parquet 型別、主鍵、單位、缺失與異常）；Gold（443 指標依賴與可計算條件）。只有符合時序的 PIT 才能放入研究。
- **正／反向血緣**：任何 Gold 行要能追公式→Silver 行/分區 SHA→Bronze raw member SHA→官方來源/公告版本；Bronze 要可列出其所有受影響的 Silver/Gold 後代。血緣結果包含投入 SHA/規則版本/Run ID。
- **真正 PIT**：交易資料、公告月營收、季財報、修訂日、停復牌、除權息、歷史上市/櫃證券集合、群組成分 as-of，逐一驗證；未知 => BLOCK，不能用今天已知值倒灌歷史。

## 4. 執行次序：最少浪費
A. **先處理 9～11 月實證**：真實 Run 42334806724 是 16/16 jobs success、14 lane receipts；來源有檔格數 11/18；`data_acceptance_result=PARTIAL`；MA5 實際反向 SHA 可追但歷史 PIT=false。11 月 TWSE 11/06 Timeout。
B. **立刻建立不假成功的 Canary Gate**：已提交測試與 Workflow 隔離輸出；新 Run 要驗證 fail-closed。此門檻只判 candidate 三層完整，不宣稱 PIT。
C. **修持久任務狀態與資料發布**：檔案更名版本化、單一 Writer、CAS/lease/fence、跨 Run crash recovery，先測才改正式指標。
D. **建 source availability 清冊**：先封存官方已知最早年度與每筆公告，若某月沒資料且未發布，標 NOT_YET_DUE / HISTORICAL_UNAVAILABLE，建立正確分母。
E. **九月 P0 修復**：TPEx 412 異常分類、Silver 受影響 Gold 重算、PIT 實證、443 formula DAG/disable reason。
F. **2026/10～11 正式 Pilot**：重跑手動限定的十月步驟、十一月 6 單元故障修復；做一筆正向＋一筆反向 end-to-end，有 SHA、發布時間、唯一 row key；全部適用月份檢驗。
G. **開始全史增量流水線**：以批次／月最小可用單元，通過的分區可發布；批次異常不拖住其他來源，定期自動產出覆蓋率與可追溯證據。

## 5. 量測與財務級品質門檻
- 第一優先：資料 PIT、hash 和來源身分皆正確；錯誤標為 UNKNOWN/QUARANTINED，不為求速度補 0。
- 每 Run 回報：`expected_applicable`、`verified`、`not_yet_due`、`unavailable_history`、`quarantined`、`new_downloaded`、`reused`、`sha_readback_pass`、`pit_pass`、`lineage_pass`、`requests`、`duration`、`Drive bytes`。
- 指標表分四類：`AVAILABLE_PASS`、`DISABLED_MISSING_SOURCE`、`WAITING_PIT`、`FORMULA_UNVERIFIED`。
- 進度不得拿 323×6 當官方應有資料量；只有經公式化 expected dataset×day/period×market×historical securities 的單位才有意義。
- 2000–2026 正式歷史回填與所有正式發布旗標，在未完成 Pilot/持久 CAS、資料 QA/PIT、雙向血緣之前維持 **BLOCKED**。

## 6. 實際修改追蹤
- `scripts/v095_r2_canary_gate.py`：對 6 個來源日進行完整性核對；Timeout、未出現、缺 Bronze/Silver/Gold 對應即 `PARTIAL_BLOCKED`，離線且不覆寫資料。
- `tests/test_v095_r2_canary_gate.py`：5 項故障注入（TWSE timeout、缺單元、6/6 候選但未 PIT、偽 PIT、缺 manifest）。
- `.github/workflows/v095-ultimate-r1.yml`：Pilot 保存原始結果後執行門檻；若 Rejected，在 Job/Workflow 顯示 failure，並上傳獨立 source-date gate Artifact。
- `scripts/v095_r2_full_architecture_audit.py`：16 項程式級診斷、明確 OPEN/已具靜態控制，永遠不把靜態 PASS 等同資料發布。
- `.github/workflows/v095-single-repo-r2-plan-audit.yml`：新增可重跑的 Python 單元測試與靜態檢查，無生產資料寫入。
- 其他如 CAS/真實 14 槽 Downloader、443 完整公式與發布 PIT **尚未完成**；需要後續實作及獨立真實證據。任何 CI 成功都不應該解除正式回填安全鎖。

## 7. 單人每日至多一小時之 SOP
- 早上 5 分鐘：看 Controller 一頁摘要，只看昨天新下載／已驗收／有待處理與失敗 Top 5。
- 中午不必巡檢，狀態由 15 分鐘 Watchdog 按需恢復，不開空 Worker。
- 晚上 10～15 分鐘：只處理 `P0`／非暫時性阻擋，剩下自動重試不必人工點選。
- 每週 30 分鐘：三層分母、資料容量、錯誤來源及成本，確認是否擴容或降載。
- 系統性 429／權限異常停止來源級 Worker，不停用其他來源；有界重試超限就 QUARANTINE。
- 不以每次輸出漂亮成功畫面為目標；以「每個已正式發布的 Gold 數字能回到當時合法已知的 Bronze 原始來源」為目標。

## 8. 最終結論
單庫 GitHub＋Google Drive 是現在最省維護且具可靠性的方案；保留 Medallion、immutable raw、idempotency、PIT、雙向血緣、故障隔離等大型機構的核心原理，**不導入**重型企業主機和平台。但目前 R1 的實際 14 個槽多為來源驗證而不是連續歷史下載，Checkpoint 缺真正 CAS，PIT/443 血緣未正式完成。R3 此次修復以「拒絕偽成功」為主，正式全史下載仍封鎖，接下來需要逐步進行可驗證的實作切換。
