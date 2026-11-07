# JARVIS v0.95 R10｜2026 年 9–11 月真實 Drive Bronze/Silver/Gold 三層驗收與完整問題矩陣

**更新日期：2026-11-07；單一執行庫：`danny541690/C1-RAW-DOWNLOADER`。**
**GitHub 真實 Run：[42364261360](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42364261360)，15/15 Jobs Success。**
**Source-of-truth Artifact：ID `13571152156`，`ultimate_r1_aggregate/202609_11_matrix.json` 及 14 個 `ultimate_r1_3month/<LANE>.json`。**
**執行程式版本：`5466bc0ec366b68bf57b32052691a6bde05db685`；本輪只執行 `scripts/v095_ultimate_r1_14lane_worker.py`、`scripts/v095_ultimate_r1_3month_reconcile.py`、`scripts/v095_ultimate_r1_3month_aggregate.py` 與 v0.95 G0–G5 規則，不呼叫 v0.93 下載器。**

## 核心驗收語義
- **CI／資料稽核執行：PASS**（15/15）；**資料驗收：PARTIAL**；**正式發布：BLOCKED**；**歷史 PIT：NOT_CERTIFIED**。
- `bronze_observed_by_month`：2026/09 **6/6**、2026/10 **3/6**、2026/11 **2/6**，共 **11/18 個來源×月份含檔案**。有檔不代表該來源所有 dataset/交易日齊全，也不是 61.1% 市場資料完整率。預期適用分母尚未知，RMI 必須 NULL，不得造 100%。
- 九月來源 canonical 月資料夾檔數：TWSE 3，TPEx 11，MOPS 7，TDCC 186，TAIFEX 19，NDC 1。這是資料夾物件數，不是市場 row 數。
- 十月來源物件數：TWSE 4、TPEx 8、TAIFEX 1，另外 MOPS／TDCC／NDC canonical 月夾觀察為 0；已在其他 QA/Staging 的候選需對帳，不可斷言官方資料絕對缺失。
- 十一月來源物件數：TWSE 5、TPEx 5，其餘官方來源 canonical 月夾觀察為 0；11 月僅到 11/07，未到公布日不列為逾期缺件。
- 既有十月局部完整來源封存及十一月指定日期 Gold 實測均可能存於不同路徑；R10 單層資料夾檢查無法代表全 Drive 搜尋，因此須先建立唯一 v0.95 Manifest 路徑索引。
- `missing_or_failed_receipts=[]`，14 個資料槽收據齊全；**不等於無資料異常**。三層 42 個槽月清單如下。

## 一、三層 42 個槽×月份完整異常與待補契約清單
本表 `observed/sample`：Bronze 為 canonical 月夾 **物件數**；Silver/Gold 為本次已列入檢查的指定 `known_parquet_pass` **個數**，兩者不是同一分母。Silver/Gold `PARTIAL` 僅證實部分候選；`BLOCK` 為尚無可被目前路徑/既定名稱對應的完整證據，不一定代表檔案不存在。

| # | 月份 | 層級 | 槽／來源 | observed/sample | 狀態 | 原因與下一步 |
|---:|---|---|---|---:|---|---|
| 01 | 2026-09 | BRONZE | TWSE | 3 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 02 | 2026-10 | BRONZE | TWSE | 4 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 03 | 2026-11 | BRONZE | TWSE | 5 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 04 | 2026-09 | BRONZE | TPEx | 11 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 05 | 2026-10 | BRONZE | TPEx | 8 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 06 | 2026-11 | BRONZE | TPEx | 5 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 07 | 2026-09 | BRONZE | MOPS | 7 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 08 | 2026-10 | BRONZE | MOPS | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 09 | 2026-11 | BRONZE | MOPS | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 10 | 2026-09 | BRONZE | TDCC | 186 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 11 | 2026-10 | BRONZE | TDCC | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 12 | 2026-11 | BRONZE | TDCC | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 13 | 2026-09 | BRONZE | TAIFEX | 19 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 14 | 2026-10 | BRONZE | TAIFEX | 1 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 15 | 2026-11 | BRONZE | TAIFEX | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 16 | 2026-09 | BRONZE | NDC | 1 | OBSERVED_PARTIAL_SOURCE_CONTRACT_UNVERIFIED | 逐 dataset×交易/公告日建母體，檢查 SHA/內容契約；不重抓已驗證檔 |
| 17 | 2026-10 | BRONZE | NDC | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 18 | 2026-11 | BRONZE | NDC | 0 | CANONICAL_MONTH_FOLDER_ZERO_CHECK_ALTERNATE_PATH_AND_OFFICIAL_APPLICABILITY | 先確認是否僅存於 Staging/其他 Bronze 路徑、再核實是否已公告；確定缺件才補抓 |
| 19 | 2026-09 | SILVER | PRICE | 2 | PARTIAL | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 20 | 2026-10 | SILVER | PRICE | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 21 | 2026-11 | SILVER | PRICE | 0 | PARTIAL | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 22 | 2026-09 | SILVER | FUNDAMENTAL | 2 | PARTIAL | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 23 | 2026-10 | SILVER | FUNDAMENTAL | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 24 | 2026-11 | SILVER | FUNDAMENTAL | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 25 | 2026-09 | SILVER | TDCC | 1 | PARTIAL | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 26 | 2026-10 | SILVER | TDCC | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 27 | 2026-11 | SILVER | TDCC | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 28 | 2026-09 | SILVER | MACRO | 0 | PARTIAL | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 29 | 2026-10 | SILVER | MACRO | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 30 | 2026-11 | SILVER | MACRO | 0 | BLOCK | 指定分區 Parquet 主鍵/單位/來源 SHA 與合法月份完整盤點；不能只靠檔名 |
| 31 | 2026-09 | GOLD | TECHNICAL | 2 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 32 | 2026-10 | GOLD | TECHNICAL | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 33 | 2026-11 | GOLD | TECHNICAL | 0 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 34 | 2026-09 | GOLD | CHIP | 2 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 35 | 2026-10 | GOLD | CHIP | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 36 | 2026-11 | GOLD | CHIP | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 37 | 2026-09 | GOLD | FINANCIAL | 1 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 38 | 2026-10 | GOLD | FINANCIAL | 0 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 39 | 2026-11 | GOLD | FINANCIAL | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 40 | 2026-09 | GOLD | CROSS_ASSET | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 41 | 2026-10 | GOLD | CROSS_ASSET | 0 | PARTIAL | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |
| 42 | 2026-11 | GOLD | CROSS_ASSET | 0 | BLOCK | 指標公式、暖機、as-of published_at、修訂版本與雙向血緣；不足者 DISABLED |

## 二、九個 canonical 資料集 × 三個月官方公布／適用性判讀（27 格）
**這些是 v0.95 發布日曆的分類結果，並不是已查證各證券的真實 first_published_at 或完整來源下載清冊。**

| 月份 | 資料集 | v0.95 時序／適用性狀態 |
|---|---|---|
| 2026-09 | CUSTOMS_TRADE | DUE_CHECK_OFFICIAL_CALENDAR |
| 2026-09 | MOEA_INDUSTRIAL_PRODUCTION | DUE_CHECK_OFFICIAL |
| 2026-09 | MOPS_MONTHLY_REVENUE | DUE_CHECK_OFFICIAL |
| 2026-09 | MOPS_QUARTERLY_FINANCIALS | PUBLICATION_DATE_UNVERIFIED |
| 2026-09 | NDC_BUSINESS_CYCLE | DUE_CHECK_OFFICIAL |
| 2026-09 | TAIFEX_DAILY | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-09 | TDCC_WEEKLY_OWNERSHIP | DUE_CHECK_PUBLISHED_WEEKLY_SNAPSHOTS |
| 2026-09 | TPEX_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-09 | TWSE_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-10 | CUSTOMS_TRADE | NOT_YET_DUE |
| 2026-10 | MOEA_INDUSTRIAL_PRODUCTION | DUE_CHECK_OFFICIAL_CALENDAR |
| 2026-10 | MOPS_MONTHLY_REVENUE | PARTIALLY_PUBLISHED_POSSIBLE |
| 2026-10 | MOPS_QUARTERLY_FINANCIALS | PUBLICATION_DATE_UNVERIFIED |
| 2026-10 | NDC_BUSINESS_CYCLE | NOT_YET_DUE |
| 2026-10 | TAIFEX_DAILY | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-10 | TDCC_WEEKLY_OWNERSHIP | DUE_CHECK_PUBLISHED_WEEKLY_SNAPSHOTS |
| 2026-10 | TPEX_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-10 | TWSE_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-11 | CUSTOMS_TRADE | NOT_YET_DUE |
| 2026-11 | MOEA_INDUSTRIAL_PRODUCTION | NOT_YET_DUE |
| 2026-11 | MOPS_MONTHLY_REVENUE | NOT_YET_DUE |
| 2026-11 | MOPS_QUARTERLY_FINANCIALS | PUBLICATION_DATE_UNVERIFIED |
| 2026-11 | NDC_BUSINESS_CYCLE | NOT_YET_DUE |
| 2026-11 | TAIFEX_DAILY | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-11 | TDCC_WEEKLY_OWNERSHIP | DUE_CHECK_PUBLISHED_WEEKLY_SNAPSHOTS |
| 2026-11 | TPEX_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |
| 2026-11 | TWSE_DAILY_MARKET | DUE_CHECK_PAST_TRADING_DAYS |

## 三、橫向錯誤履歷（針對已知數值／契約，不能靠全重抓解決）
| Issue ID | 影響 | 現況及可重現證據 | 具體修復／驗收 |
|---|---|---|---|
| R10-P0-01 | 六來源月份缺口 | 9月6/6、10月3/6、11月2/6「有檔」，不是逐 dataset 預期完整率 | 第一件事是彙整全部 canonical／staging 路徑與官方適用分母；只對真正缺件派 GET |
| R10-P0-02 | Silver／Gold 月份與分區 | 10–11月大多資料槽無對應 Parquet；十月既有 V2/描述性輸出和十一月三層候選檔可能在非月夾路徑 | 以原始 SHA+source/dataset/month+schema version 建索引，不得把無月夾當遺失 |
| R10-P0-03 | 443 公式、PIT、歷史存續集合 | 本次所有 Gold `formula_pit_certified=false`；沒有真實 `available_at/revision_at` | 443 逐項 Formula DAG、暖機、來源公告 timestamp/版本；停用未知欄位 |
| R10-P0-04 | Gold→Silver→Bronze 與反向受影響清單 | 僅有限候選 SHA，比對不構成所有 row 級有向血緣 | 每筆 Gold/partition 記 input Silver SHA，Silver 記 Bronze SHA、交易日期及原生版本；正反向交叉驗證 |
| R10-P0-05 | 下載任務原子性 | v0.95 未完成可證實的跨 GitHub Runner 單寫者、多月中斷恢復生產 Writer | 用 **v0.95** 實際 Worker 做雙 Runner CAS、stale fencing、Drive 讀回與崩潰恢復，不必遷移 v0.93 系統 |
| R10-P1-06 | 九月 TPEx `---` OHLCV | 17,762 原始列、412 非數值（255 有量，157 無量），Native bytes 與 SHA 已保留 | 依歷史普通股票主檔核對價格不可得／交易狀態；價格 NULL 不填 0 |
| R10-P1-07 | TDCC 2026/10/30 快照 | 4,111 群組、496 group 警告（58 share、451 ratio），已清理代碼 padding；**此異常的原始快照是 10/30，不是九月資料** | 百分比以集保庫存為分母，依週別/證券類型核對、只復查 496 警示 |
| R10-P1-08 | TWSE 偶發官方逾時 | R22 原端點 42359498188 已 HTTP200 通過，亦已加入有界重試 | 對真正失敗單元隔離重試，不重抓已有 immutable snapshot |
| R10-P1-09 | 11月部分當期尚未發布 | NDC／MOPS／海關／工業生產部份資料尚未到日期；「月」不代表當月每一天都有資料 | `NOT_YET_DUE` 不列逾期及任務失敗，月底及公告日後增量接收 |
| R10-P1-10 | 版本規格混淆 | 16 個官方雙向＋FinMind／DAILY／REPAIR **邏輯下載槽** ≠ 本輪 14 個 BSG **驗收槽** | 正式全史回填沿用 v0.95 16 槽規格；用本 R10 14 槽作受控 QA |
| R10-P1-11 | GitHub Action 維護警告 | 實際 GitHub Runner 有 Actions Node.js20 fallback/deprecation 警告，非資料損壞 | 升級至已支援當前 Runtime 的 checkout/setup-python/upload-artifact 版本，回歸確認 |
| R10-P1-12 | v0.95 來源可得契約 | 2000–2026 既有 2261 個 discovery 工作候選尚無經核證分母；來源歷史起日依 dataset 不同 | 適用／不存在／未公布／真正缺件分開，沒有來源適用證據不得失敗無限重試 |

## 四、正式全史下載的試跑通過條件
- 1 個真實缺件的 source×dataset×month：來源 HTTP/native bytes、SHA、Drive 不可變寫入／下載讀回、Manifest、Checkpoint、同來源雙 Runner 拒搶寫、恢復重跑先 SKIP；測試證據本輪尚未完成，正式原始資料大規模寫入暫不核准。
- Bronze 可以按 **G0～G2** 經核實的實際分區先放行；**不要以 443 Gold PIT 尚未完成阻止一切安全原始資料收集**。但發布 Gold/Research 仍要滿足 G3～G5、PIT 和雙向血緣。
- 此 R10 是 2026/09–11 的**第一輪 v0.95 三層盤點**，不重抓已合格資料，不將部分來源 QA 丟失作完成宣稱。
- 全史 2000–2026 只能按已經真正發佈且適用的月/日回填，2026/11/07 不是完整 11 月。
- `governance/v095/PHASE1_FLAGS.json` 的 `BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false` 不變；本輪 Gold 443 PIT 沒證據就保持 `NOT_CERTIFIED`。

## 真實證據與查閱入口
- [GitHub Run 42364261360](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42364261360)。
- GitHub Actions artifact `r10-v095-three-month-all-stage-report-42364261360`，ID `13571152156`：`ultimate_r1_aggregate/202609_11_matrix.json` 可稽核 42 槽月與 27 個資料集公布狀態，並有 14 個獨立 lane receipts。
- Google Drive v0.95 官方規格來源：`JARVIS_C1_v0.95_Architecture_Management_R1.xlsx` (ID `1zR1FkurqbpsWMl9y71PdDlzGHqIqz8oU`)；Run 422... 前的 PDF/舊 R9 不得覆蓋本輪真實實測。
