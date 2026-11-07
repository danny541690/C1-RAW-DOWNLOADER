# JARVIS v0.95 R7｜2026/09–11 問題資料優先、通過範圍免重下載與免重驗
日期 2026-11-07；唯一 GitHub Repo：C1-RAW-DOWNLOADER。
## 真實執行結果
- 參考基準 R6 真實 Run [42356953109](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42356953109)，Artifact 13568171926；該輪 13 個驗收門檻，7 個屬於限定範圍的候選 PASS、6 個仍有 blocker。
- R7 新增範圍限定的 Candidate Receipt 管理帳：`governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json`；**12 個已通過的候選工作單元免再次下載與檢查**，僅代表已知檔案/特定分區通過，**不是全部月份或全史資料完整**。
- R7 實際 [Run 42357744959](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42357744959) `completed/success`。工作單元 12 個 `SKIP_PRIOR_CANDIDATE`、重複下載 0、重複檢查既有檔案 0、原先六類問題仍列OPEN。
- R7 唯一立即執行的來源探測：TWSE 2026-11-06 交易日官方 MI_INDEX API `LIVE_HTTP_SAMPLE_PASS_NOT_FULL_DATASET`，HTTP 第 1 次成功，response bytes=253043，SHA256=`640803a29e0ec937e96cbcc8b054ba36063f73acb852aa35336bb7ac62c59262`。**此結果不代表之前 R22 全部 API 契約通過，也不代表整月完整。**
- 目前 R6 完整候選比對已改**僅手動**執行；平日每30分鐘簡單管理帳檢查不重抓。R7 每 2 小時做 delta-only 工作單元／TWSE 來源檢測，不碰已通過三層候選內容。原 ULTIMATE R1 固定 14 個 Runner 已關閉自動 Cron，保留手動故障診斷。
## 2026/09–11 目前仍開啟的問題
|缺失|已證實|下一個具體修復點|
|---|---|---|
|R22 TWSE live|2026-11-06 單次官方 MI_INDEX 成功|對 R22 **原本失敗的同一個來源路徑／日期／schema** 重新測；不可只拿類似端點代替|
|9月 TPEx 非數值|17762 raw rows；255 有成交量無價、157 零量無價；412/412 保存原生欄及 raw lineage|用官方歷史上市櫃證券 master 與交易狀態核對；無法證實者 `UNVERIFIED_MARKET_STATUS`，不能當 0|
|TDCC 語意|R20 官方 HTTP 200；69887 rows，Bronze SHA `475c2765a60be8fd0c7d8be49cb924e7a4d2bf853c6850b0c308b19d5850cc6d`；R24 4111 security-date groups、58 share diff、451 ratio warnings、合計 group warnings 496|提取 58 個 group 的來源日/級距／股數與 451 比率分母例外，須有逐行原始證據才認證，不因 R20 HTTP200 就算 PIT PASS|
|來源涵蓋率|三個月來源月份有檔 11/18，但不是真實資料集完整率|官方 dataset×上市日期 as-of×公告/交易日 expected denominator；缺檔才派 fetch|
|443 公式 PIT 雙向血緣|443 個 candidate mapping、1329 月核對列，均不是公式級認證|逐指標 formula digest/first published/asof and Gold→Silver→Bronze row SHA、反向邊；不足者停用|
|v0.95 正式多 Runner CAS|舊 GitCAS/Coordinator 單機/離線測試已過|實際 v0.95 Drive Writer 的 CAS lease/fencing/Crash Recovery/One-writer 證據，才可啟動多月份自動寫入|
## 安全狀態
- **正式全量回填尚未上線**，`BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`；不得以 12 SKIP 或 HTTP SAMPLE 成功宣稱整個 9～11 月已完整。
- 現有顯示正確的來源 bytes 不重抓；資料品質/PIT 未通過的欄位可獨立隔離，工作管理帳只在有確切異常和來源適用分母時派出真正缺件下載。
- 新定期執行入口 [R7](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/main/.github/workflows/v095-r7-problem-only-sep-nov.yml)；舊 R6 保留唯讀輕量清冊/手動全驗收。
