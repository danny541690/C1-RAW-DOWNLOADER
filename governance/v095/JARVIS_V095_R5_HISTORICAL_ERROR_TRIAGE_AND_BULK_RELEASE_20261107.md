# JARVIS C1 v0.95 R5｜以舊版錯誤履歷和 GitHub Run 重新追因、修復、全期放行規範
日期：2026-11-07；唯一程式庫：C1-RAW-DOWNLOADER。此文件是**實測狀態**，不是保證所有缺失已修復。
## 一、已實際執行的修復與證據
|缺失|本輪實作|證據|本輪驗收|
|---|---|---|---|
|2026/11 TWSE 11/03、11/06 官方 HTTP 偶發 timeout|前輪加入原始官方檔 SHA/readback/validator 唯一快照優先重用，無快照才有界 HTTP retry|Run 42342690996 16/16 jobs，6/6 candidate，含 4 項快照錯誤注入測試|**候選檔重驗 PASS；不等於官方即時連線或 PIT PASS**|
|2026/10 同名 Silver 不可變輸出衝突|修除當日執行時間欄、V2 內容 SHA 當檔名，保留舊原始檔不覆寫|Run 42342909253 與 42342919106 成功；3 個特定 source partition 轉換+查詢，3 TWSE、7 TPEx 封存樣本|**限定來源的候選 B/S/G PASS；全月未知**|
|2026/09 TPEx 412 OHLCV 原始非數值|新增 `scripts/v095_202609_tpex_nonnumeric_triage.py`，以真實 20 個交易日、原生 ZIP 與來源 SHA 逐筆分類；未填零未刪除|Run [42353269924](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42353269924)成功，17762 行、412 例外|**原始分類 412/412 PASS**：有量但無價格 255；無量且無價格 157；**官方停牌／價格語意未認證**|
|Checkpoint CAS、Lease、Fencing 重寫風險|重新使用既有 v0.93 `GitCAS`、`Coordinator`、state pages，跑獨立 Git/SQLite 的衝突、過期權限及頁面 SHA 測試|Run [42353313608](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42353313608)成功，3 組模組回歸測試|**舊協調核心可重用 PASS；尚未掛進 v0.95 14 槽正式資料寫入**|
|三個月最終來源與 PIT|R4 一輪隔離測試 R22 抓到即時 TWSE source BLOCKED；Final gate 無法完成|Run [42343175946](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42343175946) 11/13 checks PASS、2 FAIL|**整合測試 FAIL，保留 Fail Closed；不可當正式放行**|
## 二、尚未解決之硬門檻（可驗收之明確定義）
1. **R22 TWSE live source BLOCKED**：取出 R22 sample URL、timeout/HTTP status、429/5xx，分辨永久 schema 變更與暫時連線；不可把既有快照驗證等同即時官方 API 通過。做 3 次 bounded retry＋exponential backoff＋不同 UTC 批次；接受條件為最新真實官方 bytes、日期/內容/欄位符合契約，留 SHA 與 HTTP 證據。
2. **TPEx 255/157 例外的市場語意**：原始 412 筆由來源 SHA 追得到，仍須用官方逐股交易狀態、停復牌、臨時交易方式或來源格式文件確認；未取得可信證據者 `NONNUMERIC_UNVERIFIED`，不可放行 OHLC 策略，但完整保留 Silver raw field/volume。255 筆有量無數字不能當成零量停牌。
3. **TDCC 的 58 差異及 451 比例警告**：R22 提供 69887 rows/4111 groups、58 discrepancies、451 ratio warnings。必須依周資料日、來源單位、股數分布級距與回報總計逐組比對；比率分母未證實前不可把比例欄 0～100% 當股票數值。
4. **正式 Checkpoint**：即使 v0.93 CAS 模組單元／離線 Git PASS，仍要接到 v0.95 task runner 的每個 source×dataset×month×partition，測同時兩個不同 GitHub Runner 爭搶同分區、競爭失敗拒寫、舊 lease fencing、意外斷線讀回與永不覆蓋 immutable Bronze。無此實測不能放開 14 lanes 的生產寫入。
5. **六官方資料源 2000–2026 有效分母**：每個來源需逐 dataset 指定官方最早可得日/停牌及已公告日，而不是用 323 月×六來源計算假完整率。既有 `config/history_source_registry.json` 的部分 documented_start 仍未經本輪 live 最早日核實，`verified_live_start=false`。缺資料應分類 `NOT_YET_DUE`、`NOT_APPLICABLE`、`OFFICIAL_HISTORY_UNAVAILABLE`、`RETRY_WAIT`。
6. **443 指標公式與 PIT**：Run 42336894477 的 443 catalog 候選對應、1329 月列不等於真實公式、暖機、逐筆分區 hash 和歷史公告日。443 項仍缺完整 formula DAG/PIT；無足夠定義或來源者標 `DISABLED_WITH_REASON`，不得回測，必須逐一按可核驗清單解除。
7. **三層雙向 row/partition lineage**：已經有九月 2330/MA5 反向 SHA 樣本，但尚未讓所有 Gold rows→Silver→Bronze→官方公告版與 Bronze→受影響下游依賴 DAG 完全可回溯。已存在的 descriptive parquet 不可稱 production Gold。
8. **真實 2000–2026 下載與調度器**：14 lanes ULTIMATE R1 目前主要是 evidence-only。需要將 v0.93 `source_executor`、bounded download adapter 逐 source/dataset 月別接進 v0.95 queue、CAS 與 Drive immutable manifest，讓每次 READY 才派工，初期 6 並行，失敗隔離後不阻塞其它月份。
## 三、最短安全上線順序與單人策略
- Stage A：完成上述 R22 TWSE / TDCC 細項分類與 TPEx 官方語意；保持候選 raw 可讀、Gold PIT disabled。
- Stage B：直接重用 v0.93 GitCAS／Coordinator，而非重造分散式資料庫；在 v0.95 實際兩 GitHub Runner、斷線恢復做 1 個來源×1 個月端到端。
- Stage C：每來源挑 1 個已正式發布 dataset 月份做真正 Gold→Silver→Bronze 正反雙向血緣與 PIT；若指標公式缺失，產生 OFFICIAL_BYTES_VALID／SILVER_VALID／GOLD_DISABLED 三個真實狀態。
- Stage D：建立 2000–2026 覆蓋分母，每個適用區間只由正式源確認；缺後續回填就只下載、不要求每個資料源 2000 年都存在。
- Stage E：正式回填開關使用獨立不可變證據文件（Run ID, immutable SHA, actual Drive folder, PIT adjudication），不能由 workflow job success 自動打開。保持 `BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`，直到以上實體流程全部 PASS。
- 維持不重抓成功快照、不覆寫原始、每次三次有界重試、unknown 保留、每天 10 分鐘只看 P0 top 5；不需 Kubernetes、Spark、另一個 GitHub 庫。
## 四、最終狀態
本輪**成功修復與複驗部分關鍵根因**，但尚未具備正式 2000–2026 全量啟動條件；承諾「全部已修、全量已上線」將違反現有 R22/TPEX/PIT/CAS 真實證據，故不將未驗證狀態假設為成功。

## 五、R5 原始行追因與 27 年排程盤點
- 原始資料 Artifact `v095-202609-tpex-actual-nonnumeric-42353269924` 中 412 筆的 OHLC 原生四欄**全部都是 `---` / ` ---`**（並非四欄隨機錯位）；255 筆成交量 >0，157 筆成交量=0。由官方原始格式造成 null 應完整保留 raw native，不將非數值資料硬轉 0。真正市場原因尚須官方資料語意判定；此資料集可能含普通股票以外有價證券，應以歷史證券主檔 as-of 排除非分析範圍。
- 官方政府資料開放平臺「上櫃股票收盤行情」資料集說明涵蓋股票、權證、ETF、ETN（https://data.gov.tw/dataset/11371）；因此不能只用 `\d{4}` 就認定所有四碼代碼都屬普通上櫃股票。
- `scripts/v095_r5_full_history_discovery_queue.py` 將 six official sources／seven named official datasets／2000-01～2026-11（323 個日曆月份）建立 **2261 個 dataset-month discovery 工作候選**。每一筆均 `UNVERIFIED_HISTORY_DISCOVERY`、`download_allowed=false`、`official_expected_count=UNKNOWN`；**這是任務盤點，不是 2261 個已通過的下載工作**。來源最早年份、日別資料集分母、當時證券集合需逐筆驗證才升級。
- 已建立 GitHub R5 唯讀歷史任務盤點 Workflow `v095-r5-history-discovery-inventory.yml`，實際 Run 以該 Workflow 結束狀態為準；不得提前宣稱成功。
