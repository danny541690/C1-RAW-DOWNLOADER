# JARVIS C1 v0.95 R4 — 2000–2026 全量下載前安全修復及 2026/09–11 複驗紀錄
日期：2026-11-07。唯一執行庫：`danny541690/C1-RAW-DOWNLOADER`。正式發布旗標：**BULK_COPY_APPROVED=false / RELEASE_APPROVED=false**，不得假設全史可開工。

## 1. 本次已修的程式
- **R4-01：十一月 TWSE 官方端點不穩定**。`scripts/v095_ultimate_r1_november_official.py` 新增 `existing_immutable_official_snapshot()`：以 Drive 上唯一的同來源、同日期原始官方 JSON，不可變檔名的 SHA256 前綴、實際下載 byte SHA、原生 validator 及 parse 結果重新驗證；已證實正確就重用、再驗證既有 Silver/Gold SHA；否則才重試真正官方 HTTP。對不唯一／篡改 SHA 的舊檔不能直接重用。Receipt 分別標 `VERIFIED_IMMUTABLE_SNAPSHOT_NOT_FRESH_HTTP` 與 `LIVE_OFFICIAL_HTTP`，不可混稱本輪已在線下載。
- **R4-02：十一月 QA 故障注入**。`tests/test_v095_november_snapshot_reuse.py` 四項測試：正確 SHA、無快照、重覆快照、SHA 不符拒用。ULTIMATE R1 把測試放在實際資料操作之前。
- **R4-03：十月 Silver 命名／重現性**。`scripts/v095_ultimate_r1_october_bsg.py` 舊版 Parquet 寫入 `imported_at_utc=當天日期`，但檔名只以原始 Blob SHA 固定，隔日重算產生不同 bytes 卻撞同名 immutable 檔。修成固定觀測月份、不用執行日做內容欄，Silver/Gold V2 用**輸出內容 SHA** 命名，與舊版分開；舊分區不覆寫，PIT 仍 false。
- **R4-04：十月測試執行入口**。`.github/workflows/v095-202610-bounded-e2e-prelaunch.yml` 補跑先前 `push` 觸發不會執行的十月真實候選資料路徑（bounded v0.93 staging→三筆特定 BSG→擴大 TWSE/TPEx 原始檔→候選 Gold 反向索引）；加入 Python `py_compile` 語法驗證和獨立 Artifact，保留正式發布阻擋。
- 本次修改不得直接宣稱已完成 2000–2026 source adapters、443 公式 DAG、歷史 PIT、全分區正反向血緣及跨 Runner durable CAS/lease/fence。

## 2. 實際 GitHub Run 與可核實結果
- [Run 42336894477](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42336894477)：原版嚴格驗收 15/16 Jobs success，TWSE 2026/11/03、11/06 `TimeoutError`，嚴格 gate 4/6 `PARTIAL_BLOCKED`，未發生虛假成功。
- [Run 42342657062](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342657062)：十一月新快照復用 6/6 `PASS_CANDIDATE_NOT_PIT`，六筆三層既有不可變資料皆 `REUSED`；清楚標示 `official_http_currently_available=false`，這是 **官方歷史快照重驗，不是六筆現場重抓**。
- [Run 42342690996](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342690996)：4 項快照故障注入測試通過、11 月 6/6 `PASS_CANDIDATE_NOT_PIT`，ULTIMATE R1 16/16 Jobs success。
- [Run 42342744419](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342744419)：十月原版三分區 `IMMUTABLE_OUTPUT_CONFLICT` 3/3；未覆寫，正確隔離。
- [Run 42342848178](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342848178)：十月 V2 初版因 Python 編輯語法錯誤未進入三層，已修並加 `py_compile`。
- [Run 42342909253](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342909253)：十月修正後初步步驟「三分區 BSG」已 success；擴大來源、查詢索引仍須依完成 Run 結論驗收。
- [Run 42342919106](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342919106)：具有 `py_compile` 防護的十月重驗，需以完成 Run 的 Job 日誌作最終證據，不預判結果。

## 3. 截至本次真實工程範圍之未解除 P0/P1
|優先|阻擋|實證與改進|
|---|---|---|
|P0|九月 TPEx 412 筆非數值 OHLCV|候選資料保留 native price text、volume、row_index，但需分別分類：有量但無價格、暫停交易、特殊交易、schema 異常，與官方原始 bytes 確認，不得補 0|
|P0|2026/09–11 六來源資料集完整性|14 槽報告中 11/18 來源月份格有檔，不等於該月份應有各資料集/日期/證券分母已完備|
|P0|歷史 PIT|first_published_at、available_at、revision_at、security universe as-of 未取得完整可稽核來源，Gold 僅 descriptive 不供回測|
|P0|443 Gold 公式與真正血緣|Catalog 443 ID + 候選映射不足以代表逐指標公式 DAG；必須按 formula digest、期數暖機、Silver/Bronze row/partition SHA 實證，未知停用|
|P0|跨 Runner Checkpoint CAS/Fencing|Drive 同名最新狀態存在，但未證明可原子防雙 Writer、租約過期、重啟恢復；未完成前不可開 27 年批量寫入|
|P0|2000–2026 真正 source adapters|現有 ULTIMATE R1 14 槽多是讀取候選資料，不等於 27 年增量來源下載／重算流水線|
|P1|GitHub Public repo 保護|不要放入私人投資策略、憑證、機密原始研究；要合一私人模型前應先轉 Private|
|P1|十月本次擴大候選 E2E|三筆來源分區先通過不等於十月全部資料集／全部月日 PIT 認證；按新 Run 後續結果逐項列出|
|P1|全期官方分母與發佈日曆|每來源／資料集／交易日／當時有效證券需產生 expected/applicable，未到期/不存在/缺檔不同列|

## 4. 最快且正確的剩餘路線
- 先接通 CAS／Fencing/Manifest 為單一 Committer，驗證兩 Runner 競爭與 Crash Recovery；
- 先完成 2026/09 TPEx 412 異常與 2026/09～11 各資料集官方發布時間及完整性分母；
- 針對已驗證上游 Parquet 增量計算可用 Gold，不能驗證之公式標 `DISABLED_WITH_REASON`；
- Gold 資料以真正計算的 row/partition SHA 正反向追溯，PIT 已知/未知分開，不可將時序未知指標發布；
- 實作六來源按資料集/月份下載器，沿用 immutability、SHA 與有界重試，先小批量 6 並行跑，穩定後再擴 8、10、14；
- 所有全期發布與大量寫入仍 BLOCKED，只有有完整可驗證報告的分區可進入正式資料庫。

## 5. 驗收語義
`GitHub Workflow success` 只代表排程與指定測試成功；`PASS_CANDIDATE_NOT_PIT` 只代表現有原始快照與描述性三層一致；真正的 `PRODUCTION_RELEASE_PASS` 需要已驗證的全部 applicable source×date、PIT/公式血緣、不可變 SHA、持久狀態等獨立證據。任何缺項不得改旗標通過。
