# JARVIS C1 v0.95 — R6 單庫合併修復、定期排程切換及全量下載前放行管理
日期：2026-11-07。程式主庫：`danny541690/C1-RAW-DOWNLOADER`（目前 Public；不得存私人持倉、API token 或未授權公開研究）。
## 1. 已正式修改的 Workflow
- **新主要定期排程**：`.github/workflows/v095-r6-merged-prelaunch-controller.yml`，run `42356953109` 為第一次完整實跑，後續修正版 `42357193745`。
- **每 30 分鐘輕量巡檢**（UTC 分 7、37）：檢查 release gate、323 個月×7 個主要資料集之歷史候選清冊，輸出本 Run 不可變 Artifact。不使用 Drive Secrets 做大量掃描。
- **每日完整候選驗證**（UTC 18:11；台灣時間翌日 02:11）：同一 Controller 依序實跑舊版 CAS/Lease/Fencing 回歸測試、2026/09 TPEx native OHLCV SHA/例外分類、2026/10 三個既定來源分區 BSG、十月 TWSE/TPEx 擴大 native archive、2026/11 六個來源日 raw snapshot/BSG，443 指標前後向候選血緣與發布日期未知報告。有限來源錯誤不覆寫已存在 raw；各步失敗留下證據與未通過旗標。
- **ULTIMATE R1 原 14 槽每 15 分鐘自動 Cron 已停**，保留 `workflow_dispatch` 手動診斷入口，不刪任何歷史資料。原因：它大部分只做候選檢查，不是 2000–2026 真正的來源 Adapter Download；無 READY 仍固定佔 14 runners，與 R6 重複。
- **GitHub 一次部署驗證**：新 Cron/Workflow 已提交 main，經 GitHub Actions 實際觸發；安全旗標保持 `BULK_COPY_APPROVED=false`，`RELEASE_APPROVED=false`。不以「排程執行成功」宣稱資料正式驗收通過。
- **額外測試**：`tests/test_v095_r6_merged_acceptance.py`，證明缺檔/偽 PIT 和 6/6 descriptive 候選都不能升級成 full history release。
## 2. 對既有履歷合併之 P0/P1
|項目|已完成或沿用|仍需真正完成|
|---|---|---|
|TWSE 2026/11 不穩定|immutable official snapshot SHA 再驗，6/6 candidate|R22 live TWSE 新 HTTP Timeout / 供應者有效路徑／可靠 408/429/5xx 退避；不能把舊快照當新 API 連線成功|
|TPEx 9月 412 例外|17762 rows，255 成交量>0、157=0，412/412 native raw lineage，無亂補 0|持股/歷史證券種類、交易狀態與 --- 價格的官方語意；需區分 ETF/ETN/權證|
|2026/10 轉換|3/3 已知來源分區、3 TWSE與7 TPEx archive 成功，content-addressed V2|未補十月全應有 dataset/day 來源、PIT 仍 false|
|2026/11 快照|六個上市上櫃來源日 native SHA與 Silver/Gold 描述性候選 PASS|正式來源涵蓋率、完整資料契約、公告時點|
|管理帳/CAS|v0.93 GitCAS＋Coordinator／Lease fencing 回歸 Run 42353313608 success|接入 v0.95 主要正式下載 writer，驗證真正跨 Runner 的一勝一負、stale lease與 Crash Recovery|
|TDCC 週資料|R22 原始 69887 rows/4111 groups；58 差異、451 比例警告已分離記錄|各週日期／官方級距合計與比例分母逐筆驗證|
|PIT與443指標|443 IDs、1329 候選三個月 source family 對應|完整 formula DAG、input SHA、暖機、修訂版 available_at 與歷史證券集合；不適用指標必須停用附原因|
|雙向血緣|九月 2330 MA5 反向 SHA 樣本；R6 跑候選映射|逐筆/逐分區 Gold ↔ Silver ↔ Bronze 與發布版本端對端無孤兒、無環|
|2000–2026 分月回填|323 月、六來源七主要 dataset、2261 個 **未放行 discovery 工作候選**|各來源最早可得日期/日別市場/實際可用率、合法 native adapters + durable queue + Drive 原子 publish|
## 3. 快速且安全的下一步
1. R6 所有步驟的 Main 分支真實 Run、逐項 SHA 與報告存檔，任何步出錯留下隔離清單。找出 **最早未被驗證的 source×dataset×month partition**，只重抓真正缺值，正確檔不重抓。
2. 把 v0.93 已通過的 GitCAS/Coordinator 以一個 verified production scoped source 和獨立 GitHub Runner 實測接到 v0.95 實際 writer；成功條件包含原子 CAS、stale fence 拒寫、Drive SHA readback。
3. 先放行符合官方來源契約的**Bronze 原始檔歸檔**，並將 Silver/Gold/PIT 認證保留獨立閘門；不得把尚未證明官方可取得的歷史候選當作 READY。
4. 正式 2000–2026 全量批次需可恢復、增量與來源限流；初始並行六個符合 READY 的工作，依負載量測逐步 8/10/14，而不是一口氣開 14 個無條件下載。
5. 只有正式不可變 SHA、Manifest、Checkpoint、官方發布日期、雙向血緣及 PIT/Gold 契約獨立驗收 PASS，才能核准最終研究資料發布。暫時不能為求速度把 fail-closed 旗標改成 true。
## 4. 真實證據
- 2026/09 TPEx 原始 412 筆逐行分類 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42353269924
- v0.93 CAS／fencing regression：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42353313608
- 十月實際三層指定來源 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342919106
- 十一月官方原始快照與候選三層：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42342690996
- R22 隔離完整整合 Run （失敗，11/13）：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42343175946
- R6 新 Controller 初次 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42356953109
- R6 加入日更和單元回歸新版 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42357193745

**注意：** 本輪「新定期排程已上線」指 GitHub R6 控制/候選品質驗證排程上線，並不表示 2000–2026 全歷史內容已開始下載。本文保留明確阻擋證據，避免虛假全量已完成。
