# JARVIS C1 v0.95 2026/01/01–2026/11/07 全年三層資料庫建置試跑：真實執行／重用資料／錯誤與後續放行總帳

版本日期 2026-11-07，唯一 GitHub 庫 `danny541690/C1-RAW-DOWNLOADER`。此為 **2026 年 1–11 月第一輪全面檔案來源盤點與限定範圍 Bronze/Silver/Gold 血緣驗收，不是全年度市場資料完整下載、也不是 Gold 443 PIT 正式發布**。原始來源資料範圍截至 2026/11/07 已公布；不能把 2026/11 視為完整月。

## 一、一天內實際執行與故障履歷
| Run ID | 操作 | 實際結果 |
|---|---|---|
| [42364261360](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42364261360) | 2026 09–11 14類三層候選驗收 | 15/15 Jobs success，內容 PARTIAL、正式 G3–G5 BLOCKED |
| [42366571846](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42366571846) | R11 十二問題規格及測試 | 18規則＋8故障注入 PASS，非正式下載 |
| [42369825417](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42369825417) | R11 T1實際 Drive metadata | 253筆，9–11月有檔來源 6/6、3/6、2/6；第一次語法錯已更正 |
| [42370877195](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42370877195) | R12有界深層Drive metadata | 551物件；第一次 NameError 已更正 |
| [42375085800](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42375085800) | R12.1 真實Operations歸檔 | 管理帳 SHA 讀回 PASS；市場資料變更0 |
| [42380057698](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42380057698) | R12.2 R5/R7/R8/R11/R12整合 | 舊12候選重用；週期巡檢合併 |
| [42381358035](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42381358035) | R13 CAS/PIT故障模型 | 模型6測試、8情境PASS，**非真實跨Runner原子交易** |
| [42382057827](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42382057827) | TWSE 11/06三層既有快照驗收 | Bronze/Silver/Gold均REUSED；Silver1099、Gold1097；2非數值價保留 |
| [42382241856](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42382241856) | TWSE 11/04三層既有快照驗收 | 三層均REUSED；Silver1100、Gold1100；未具PIT |
| [42383128149](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42383128149) | 2026年11個月六官方來源、三層檔案掃描 | SUCCESS；66個來源月份格，v0.95來源樹 1–8月未觀察到檔案，不是官方缺失 |
| [42383493996](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42383493996) | 加入早期RAW封存掃描第一輪 | 原始來源根目錄超過2000項導致 `SINGLE_FOLDER_BUDGET_EXCEEDED`；改為月資料夾專查＋部分分頁隔離 |
| [42383772658](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42383772658) | 2026全年既有RAW封存與v0.95三層同一Run | **completed/success**，重用證據與年度報告在Drive Operations SHA讀回成功 |

## 二、2026 Jan–Nov 官方來源／檔案路徑與三層完成觀察
- 舊 RAW 2026 總來源月份格 **66**（六官方×11個月）；可找到來源月夾 **62/66**，有非資料夾物件之來源月份 **51/66**。
- 舊 RAW 來源月夾中共觀察到 **至少3,765件原始檔候選**；其中 **2個月份資料夾**超過第一頁1000筆，須追加分頁取得真實總數，不得將3,765當確切總筆數或市場資料完成率。
- 對舊版RAW中24個既有ZIP做**真實63,439,595 bytes SHA256、ZIP目錄安全、CRC讀取**，24/24通過，0個ZIP樣本錯誤；只是限定樣本**物件完整性**，無法證明完整日／欄位／證券、公告時點、PIT及來源契約已PASS。
- v0.95 canonical/staging/Silver/Gold **有界metadata物件456個**，實際分層「檔案數」下表。Jan–Aug在**此批指定v0.95目錄**為0，但並非整個Google Drive中不存在；舊RAW候選必須對帳後接收。

| 月份 | 舊RAW來源月夾 | 舊RAW含檔來源 | 舊RAW檔案候選（下限） | v0.95 Bronze檔 | v0.95 Silver檔 | v0.95 Gold檔 | 狀態 |
|---|---|---|---:|---:|---:|---:|---|
| 2026/01 | 6/6 | 5/6 | 31 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/02 | 6/6 | 5/6 | 30 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/03 | 6/6 | 5/6 | 250 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/04 | 6/6 | 5/6 | 34 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/05 | 6/6 | 5/6 | 33 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/06 | 6/6 | 5/6 | 359 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/07 | 6/6 | 5/6 | 34 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/08 | 6/6 | 6/6 | 32 | 0 | 0 | 0 | 舊封存待按 v0.95 契約驗收 |
| 2026/09 | 5/6 | 5/6 | 1,163* | 228 | 97 | 13 | 候選檔，非月度全數PASS |
| 2026/10 | 5/6 | 5/6 | 1,799* | 13 | 8 | 8 | 候選檔，非月度全數PASS |
| 2026/11 | 4/6 | 0/6 | 0 | 10 | 10 | 10 | 候選檔，非月度全數PASS |
* 9、10月各有超過單頁限制的月份檔案夾，已標記分頁未完。另有Staging與資料夾項目；不得混合計算成已驗證資料集。11月尚未完結。*

## 三、三層血緣實測證據
- 2026/11/04 TWSE：`Bronze SHA bfeb59787966639b0186ec2a7b0aeb8b640dba03b1b1855ae6ed75106109dc0f` → Silver 1100列 → Gold 描述性 1100列；三份 immutable artifact均 `REUSED`，官方來源是已留存且有 SHA 的 snapshot，未重新發 HTTP。
- 2026/11/06 TWSE：`Bronze SHA dce272ac7dc602e16d33798b721eed1a201de7aefd1e137434a3786eafcb20c0` → Silver 1099列 → Gold 描述性 1097列；兩筆非數值價格另行保留；三份全部重用。
- 這兩個日期能證明**限定分區的Bronze→Silver→Gold檔案SHA父子追蹤**，不等於所有2026月份、所有資料集、443個指標完成，也未證明反向影響圖完整或歷史公告PIT。Gold `PIT=false` 正確維持 `DESCRIPTIVE_NO_BACKTEST`。

## 四、已分析的錯誤及新排程吸收的規則
1. 2026 Jan–Aug新v0.95空目錄是**目錄範圍誤判**，改以舊RAW來源分區候選做SHA重用，避免全月無謂重抓。
2. 舊RAW根目錄可超過2000項，初版掃描失敗；改用只查**來源／月份資料夾**與帶 `incompleteSearch` 的有界欄位查詢。兩個超過1000項月份只回報**下限**，不假稱完整。
3. 原生ZIP內容 SHA／CRC通過不代表 schema、歷史公告日、交易日或官方分母全通過。v0.95 Bronze需逐資料集核對原生欄位、日期與來源版本。
4. v0.95 生產 `MANIFEST_INDEX.csv` **0筆**、`CHECKPOINTS.csv` **0筆**；不允許寫入虛構的COMMITTED／SHA來造完成率。
5. 8來源Registry均 `PENDING`；39個Source Dataset Contracts為 `CANDIDATE_NEEDS_SCHEMA_AND_PIT_VALIDATION`，正式可下載已核准來源資料集**0**。
6. R13雙Runner CAS只有 in-memory 測試通過，**真實GitHub異Runner仲裁、lease fencing、Drive原始bytes遠端讀回以及restart SKIP未整體認證**。
7. TPEx Sep `---` 412列（其中255有量、157無量）與 TDCC 10/30快照496個警示群組是**來源資料語意類**，不能當HTTP失敗不斷重抓。
8. MOPS財報單季/累計、修訂時點與NDC歷史vintage必須PIT；Gold未獲官方發布as-of與實際公式DAG不能進正式回測。
9. 未驗證原始SHA的舊RAW檔案不可盲目複製到v0.95、也不可用Drive MD5假冒SHA256。
10. 沒有官方預期 dataset×日／週／月×證券歷史母體，資料完整率只能 `UNKNOWN`；檔案數和來源有檔格不能代表市場完成率。
11. 同來源兩個方向不得同時寫入；合併單一Controller、動態Worker、CAS以及不可變版本，生產正式Writer尚需真實實作。
12. G0→G2 Bronze與G3→G5 Gold研究發布應分層放行；不能以443項Gold尚未完成阻止安全的原始歷史保留。

## 五、真正剩餘的「一條」關鍵流水線
**不是再增加新一批巡檢排程。** 應改為一個可靠的：
`官方source/dataset日期契約→檢查v0.95/舊RAW已驗證SHA→缺件才抓取→不可變Drive保存＋SHA回讀→GitHub原子Checkpoint/CAS→Silver Parquet原始欄位轉換與QA→Gold公式PIT可用才計算→雙向lineage→增量續跑`。

分段放行：先核准一個來源及資料集、對1個已公告的真缺件完成真實CAS；合格者可開始Bronze全年增量，無關Silver/Gold等待原因標記；正式Gold只有 PIT /公式/血緣證據全通過才發布。**直到這條真正生產寫入閉環通過，不得宣稱已完成2026全量，也不得自動升級2000–2026。**

## 六、正式檔案與限制
- GitHub 同一條整合排程：`.github/workflows/v095-r12-sep-nov-deep-manifest-retirement-preflight.yml`，Push/手動可即刻啟動單輪「2026年11月7日前」年度範圍；週期性版本仍只處理既定候選QA，不能以2小時定時醒來假裝正在持續全史下載。
- 真實全年 evidence Artifact：Run `42383772658` artifact `13578333655`，包含按來源月份統計、舊原始封存ZIP檢驗結果、兩天BSG已驗證範圍及正式治理閘門。
- Google Drive `60_OPERATIONS_QA` 紀錄：Run `42383772658`，`PASS_OPERATIONS_AUDIT_SHA_READBACK`，SHA256 `a0c75758434b8fc754c04a0928f054238657d9c0cb3c1932893e3d48caf58ab1`；正式 `BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`。
