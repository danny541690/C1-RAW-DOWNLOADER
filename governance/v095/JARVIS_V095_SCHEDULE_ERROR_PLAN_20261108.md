# JARVIS C1 v0.95｜六大來源排程、錯誤履歷與後續方案（2026-11-08）

版本：2026-11-08-R1  
唯一執行庫：danny541690/C1-RAW-DOWNLOADER  
發布位置：Google Drive JARVIS Operations（附原始 SHA256 與讀回驗證）  
資料範圍：2000-01-01 至 2026-11-08 可取得的歷史及 2026 年逐日增量；2026-11 後續尚未發生日期不可列入實際驗證。  
重要：本文件是**排程／錯誤修復交接與下一步執行方案**；不是六大來源全部完整、不是正式 Gold 400+ 指標，也不是 PIT 驗收通過證書。

## A. 現行六條來源排程（GitHub Actions；UTC）

| 來源 | 現有排程 cron（UTC） | 主要程式 | 已驗證能力 | 尚未放行 |
|---|---|---|---|---|
| TWSE | `4,19,34,49 * * * *` | `v095_2026_price_incremental.py` | 官方日行情下載、候選 B/S/G、SHA/血緣、獨立 Checkpoint | 全年完成率、正式 400+ Gold／PIT |
| TPEx | `6,21,36,51 * * * *` | 同上 | 官方上櫃日行情、候選 B/S/G、SHA/血緣 | 全年完成率、正式 400+ Gold／PIT |
| MOPS | `8,38 * * * *` | `v095_2026_four_source_archive_intake.py` | 舊原生 ZIP 候選 Bronze，rootless 季報 manifest 可逐 unit 驗證 | typed Silver／Gold、公布時間 |
| TDCC | `10,40 * * * *` | 同上＋獨立週資料收據檢查 | 3 份候選原始檔重用；已知單一無 manifest ZIP 隔離 | 全歷史週次／公告時間／typed Silver |
| TAIFEX | `12,42 * * * *` | 同上＋官方年度/月度日期解析器 | 年度 ZIP/CSV 與價差委託日彙總分版型，候選資料隔離 | 巨量不符版型 ZIP；typed Silver／Gold |
| NDC | `14,44 * * * *` | 同上＋官方歷史 ZIP 日期管理 | 321 個觀察月份的官方歷史 ZIP SHA 重用 | 歷史初次公告日／PIT vintage／typed Silver |

來源工作獨立 single-writer concurrency；排程 cron 使用 UTC，不代表台灣本地時間。**GitHub Actions 的 schedule 可能延遲、略過或排隊，實際完成以每個 Run 的收據、Checkpoint、sha 與 Drive 讀回為準。** 每條來源流程在同源寫入時不可讓另一批覆蓋。

## B. 已經核實的最新執行與 Checkpoint

- 六來源合併 Run：`42458778942`，六個子工作均 `success`。URL：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42458778942
- TWSE：本輪 10 組 B/S/描述性 Gold 候選，血緣 10/10；`next_offset=186`，`total_candidate_weekdays=222`，`failed_units=1`，`retry_queue_length=0`，`year_complete=false`、`PIT=false`。注意 222 是該程式候選日數，不是已官方確認完整年度交易日數。
- TPEx：本輪 10 組 B/S/描述性 Gold 候選，血緣 10/10；`next_offset=186`、`total_candidate_weekdays=222`、`failed_units=1`、`retry_queue_length=0`，全年度未完成、PIT=false。
- MOPS：本輪新增 6 份合格 manifest+SHA 的 Bronze 候選，`scanned=6`、`blocked=0`、`unchanged_archive_skipped=24`；不是已完成正式季財報 Silver。
- TDCC：本輪 `new_archives=0`，`cached_quarantine_skips=1`、`known_immutable_format_exceptions=1`、`unchanged_archive_skipped=3`；確認重用 3 份、隔離 1 份而非重複下載。
- TAIFEX：本輪 `new_archives=0`、`scanned=213`、`blocked=214`（其中 1 筆缺舊資料夾）、`known_immutable_format_exceptions=213`、`unchanged_archive_skipped=29`。錯誤分類：`TAIFEX_SPREAD_DATE_OUTSIDE_REQUEST_MONTH=31`、`UNSAFE_ARCHIVE=116`、`TAIFEX_NATIVE_ZIP_NOT_SINGLE_CSV=61`、`RESPONSE_DATE_OUTSIDE_REQUEST=1`、`ZIP_EXPANSION_LIMIT=4`、`V093_MONTH_FOLDER_NOT_UNIQUE_OR_MISSING=1`。不同原因不可合併宣告「下載失敗」。
- NDC：官方 ZIP 原始 SHA 重用；`official_observation_months_reused=321`、`blocked=0`；PIT 未通過。
- 之前失敗 Run：`42458415866`，MOPS／TDCC／TAIFEX 因舊 `V095_QUARANTINE_...` JSON 寫入文字 `\\n` 尾碼，讀回 `json.loads` 出現 `JSONDecodeError: Extra data`。**是內部 Checkpoint 格式，不是官方網站同時失效。**
- 修復：commit `e8279cc9e7ee1e8f40bbccd5c1c6727c73230099` 新增嚴格讀取器，維持原 bytes/SHA、允許指定舊尾碼，拒絕其他多餘內容；之後回歸測試修正，Run `42458778942` 全部成功。隔離版本以驗證器邏輯指紋管理，避免非相關程式修改造成已知問題再次抓取。
- 官方／JARVIS 39 項契約格式對照：`42455411552` 成功，但 TDCC 內部 JSONL 分區不等同官方原生 CSV/JSON，仍須欄位映射血緣證據。

## C. 錯誤履歷與對策清單（用於後續排程）

| 類別 | 根因 | 修復策略與狀態 | 是否阻塞安全 Bronze |
|---|---|---|---|
| G0 休市假缺漏 | 將非交易日當作抓取失敗 | 已建官方日期正向證據與 2026 休市前置驗證；未知日僅 PROBE，不列缺檔 | 否 |
| TWSE 歷史格式 | `/rwd/...` 回傳 HTML、舊 `/exchangeReport/FMTQIK` 取得正確 JSON | 核對 JSON `stat`、年月、來源 SHA；2000–2026 正向交易日證據共 6,631 | 否，須查年月 |
| TPEx 回應月份 | 舊接口可能回非指定月份 | 回應 `date` 與每列日期同時驗證；獨立 6,303 正向交易日證據 | 否，錯月須隔離 |
| MOPS 舊檔名／編碼 | 歷史 `_0` 有無、CP950、月營收與季報混淆 | 以來源年份、報表類型與單位各自驗證；不以報表期代替實際公告日 | 否，錯誤個別隔離 |
| MOPS rootless manifest | 舊版根層無 source/month，但每 unit 有 source/month | 只有全部 unit 身分一致且每成員 SHA 通過才接受候選 Bronze | 否 |
| TDCC 最後無 manifest ZIP | 只有原始 CSV/JSON，缺無法驗證的 member SHA／source/month | 既有 3 份可重用；單一 ZIP QUARANTINE，不自行補造證據 | 否，隔離此單元 |
| TAIFEX 多種報表版型 | 期貨行情與價差委託概況（標題列＋header）不同；部分 ZIP 錯置月份 | 分報表解析，原始內容日期唯一且驗證後才更正目標月份，保存舊 folder 與新月份關係 | 否；目前大量例外仍需分類 |
| TAIFEX 超規 ZIP | 單檔／總解壓量／不安全路徑疑慮 | 一律先安全檢查 ZIP CRC、加密、檔案數、膨脹上限；不得強行放寬 | 隔離該 ZIP |
| NDC 假缺月份 | 以舊 0.93 月資料夾檢查整包年度 ZIP | 官方修訂版 ZIP 321 觀察月份可重用；舊三個資料夾缺失不作來源缺漏 | 否 |
| 內部舊隔離收據 `Extra data` | JSON 末端錯誤的文字跳脫 `\\n` | 严格限定舊尾碼的讀取相容、保存 SHA、轉寫正確 JSON、回歸測試 | 已修復 |
| 初次公布時間不明 | 觀察月／交易日／發布時點混淆 | 分離 `trade_date`、`observation_month`、`snapshot_date`、`published_at`、`retrieved_at`；未知不過 PIT | 不阻塞候選 Bronze |

## D. 後續整體執行流程（不等待兩小時／隔天才能繼續）

1. **G0 日期與來源契約**：每來源最早可得日、頻率、真實交易日／觀察月份／週次、官方原始回應、資料發佈時間各自管理。未驗證日期不作完整率分母。
2. **接續 Checkpoint**：TWSE/TPEx 以 `next_offset=186` 及最新 Drive durable checkpoint 為準；已驗證的 SHA 不再抓，失敗日期進限定重試佇列。禁止用歷史報告值覆蓋更晚的 checkpoint。
3. **四來源候選封存**：MOPS、TDCC、TAIFEX、NDC 依資料集使用 typed adapter；先檢查官方類型、原檔 SHA、source/date、檔案解壓上限。已知壞檔放隔離清單並保持原因與原始 ID。
4. **Silver 資料正規化**：只准上市與上櫃，日 K 以上；代碼真實 TSE/OTC；金額統一億元（例如 MOPS 原始仟元 ÷100,000）；日期欄與編碼依資料類型標準化；缺資料是 NULL，不用 0 代替。
5. **Gold 候選與 PIT**：400+ 指標只有資料存在、映射通過、可取得時間驗證後才激活；財報／集保週資料／國發會歷史修訂不可提早看見；正式 PIT gate 未過則不能把描述性 Gold 當回測成績。
6. **自動錯誤分流**：HTTP/授權異常重試有上限；來源無該年資料做 SOURCE_NOT_YET_AVAILABLE；官方關站／休市為 SKIP；解析錯位為 SCHEMA_REVIEW；下載正常但 SHA 錯為 QUARANTINE；無舊版歷史發布日記錄為 PIT_PENDING。不得卡住其他來源。
7. **每輪成果報告**：來源、run_id、開始與結束 offset、預期來源日期與已取得日期、已下載、已確認完整、異常、缺資料、已隔離、重試數、sha_readback、B/S/G、PIT、單位映射、證據 URL；各狀態分開統計。
8. **驗收順序**：先完成 2026-01-01 至最新的 G0→Bronze→Silver 候選／Gold 描述性＋血緣；明確列尚缺 39 種契約及正式 PIT，再進 2000–2026 全量。已確認單元不重抓、不重驗，失敗單元優先。

## E. 不得混淆的完工標準

- `workflow_conclusion=success` 只是腳本流程結束，不代表 `all_data_complete=true`。
- `Bronze_candidate_created` 不代表 source-native fields、Silver、Gold 400+、PIT 已驗收。
- `NDC_observation_month_exists` 不代表歷史初次公布日已證實。
- `TDCC_snapshot_date` 不是法定實際發布時間；2008 年 7 月前股權分散表不可列為應有缺漏。
- 所有金額採億元表示；來源原始單位保留於 Bronze，不得直接覆寫。
- 六來源仍有未解問題，因此正式 `RELEASE_APPROVED=false`，不可宣稱六來源資料庫已完成。

## F. 相關修復與驗證連結

- 最後成功六來源 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42458778942
- 最新官方格式、日期、ZIP 修復規範：https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/main/governance/v095/OFFICIAL_VS_JARVIS_FORMAT_REPAIR_20261108.md
- 下載准入及 PIT 隔離規則：`scripts/v095_g0_bronze_download_gate.py`
- 四來源封存下載及隔離復原：`scripts/v095_2026_four_source_archive_intake.py`
- 避免假缺漏的六來源日期總表：`scripts/v095_g0_six_source_date_quality.py`

記錄規則：此報告是按 2026-11-08 已完成的執行收據建立。未來來源完成或失敗要以新 Run 的收據新增版本，不得靜默改寫舊報告。

## G. 日期化進度管理（2026-11-08，新格式已成功寫入 Google Drive）

**基準：2026-11-08 15:37 台灣時間；即時來源為 SHA 驗證的 Google Drive durable checkpoint，不以歷史回答當即時狀態。**

| 來源 | 進度所指的日期 | 下一待處理日期 / 驗收 | 日期性質 |
|---|---|---|---|
| TWSE | 已巡檢平日候選至 **2026-09-17**（offset=186；Run #42458778942） | **2026-09-18**；另外 **2026-07-10** 有失敗收據 | 巡檢游標，不表示全部原始日檔成功 |
| TPEx | 已巡檢平日候選至 **2026-09-17**（offset=186；同上） | **2026-09-18**；另外 **2026-07-10** 有失敗收據 | 巡檢游標，不能算完整率 |
| MOPS | 2026-01～2026-09 各有部分候選封存檔 | 檢查尚缺的原始發布日期及每個月份應有的報表 | 月份存在候選檔，不是完整月度履歷 |
| TDCC | 2026-08～2026-10 有候選封存檔 | 補歷史週基準日與公告時間，仍有個別無 manifest ZIP 隔離 | 週基準日與發布日分離 |
| TAIFEX | 2026-09～2026-10 有候選封存檔 | 整理 ZIP 內有效交易日期與錯放月份檔、來源格式異常 | 月份有候選封存，不表示全月行情完整 |
| NDC | **321 個觀察月份**（官方原始資料 ZIP 的修訂版） | 補真正首次公布日期與原始歷史版本 | 觀察月不等於 PIT 發布時點 |

### Google Drive 最新日期進度表

- CSV：https://drive.google.com/file/d/1SUbQ_AJE7QdkxdYimHbTgFo_lpuydp-i/view
- JSON：https://drive.google.com/file/d/1hd5Vxt7UsNoq0p_8qmjJzSE5CR3L79vU/view
- Markdown：https://drive.google.com/file/d/1QWNuseY5sqBFgM2-WzF3eZ0O1phQqe8A/view
- 實際 Run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42459724943 ，已成功，Drive SHA 回讀通過。

**日期制下一輪原則：** 每來源一定要記 `last_inspected_date`、`last_verified_date`（只有有證據才填）、`next_expected_date`、`failed_dates[]`、`source_earliest_eligible_date`、`PIT_published_at`（未知為 null）。以實際 source calendar 和 frequency 計應有數，不得按平日或月份自動將未知日標成缺漏。

## H. 六來源 Bronze／Silver／Gold 分層日期進度（新增 2026-11-08）

**正式日期進度表**：https://drive.google.com/file/d/1Gx4tDU3rrEb1CtcboaDWTbHyqEG7XYrd/view  
**JSON 管理帳**：https://drive.google.com/file/d/1SrrpwjZYJMxij8Q3aRTUkI8nt3tBjC04/view  
**說明報告**：https://drive.google.com/file/d/1sv3tAGhq2UN9LR6FizO46kvqKspaPSUF/view  
**GitHub 實測 Run**：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42460495966 （成功，18 列，三檔 SHA256 Drive 讀回驗證 PASS）。

- 全歷史目標：**2000-01-01 至 2026-11-08**；2026 年度優先驗收：**2026-01-01 至 2026-11-08**。TDCC 股權分散表按最早官方可取得的 2008-07 另立實際來源起點。
- **TWSE**：Bronze 最新候選檔日期 **2026-11-06**；Silver 最新候選檔 **2026-11-06**；Gold（僅描述性候選）最新候選檔 **2026-11-06**。但持續增量巡檢游標只到 **2026-09-17**，下一個日為 **2026-09-18**，另有歷史失敗日需要獨立補修；**不得以 11/06 認定 1/01–11/06 連續全部完成**。
- **TPEx**：Bronze／Silver／描述性 Gold 最新候選檔同為 **2026-11-06**；增量巡檢游標同為 **2026-09-17**，下一個日 **2026-09-18**。仍需檢查缺日及歷史來源。
- **MOPS**：Bronze 候選原始月檔最新月份 **2026-09**；尚無可核定 typed Silver 及 Gold 正式日期。
- **TDCC**：Bronze 候選原始月檔最新月份 **2026-10**；尚無可核定 typed Silver 及 Gold 正式日期，週基準日另查。
- **TAIFEX**：Bronze 候選原始月檔最新月份 **2026-10**；尚無可核定 typed Silver 及 Gold 正式日期；解析異常 ZIP 仍隔離。
- **NDC**：官方 ZIP 的最新觀察月份 **2026-09**；歷史修訂版可重用 321 個觀察月份； typed Silver、Gold 日期未認證，真正歷史公布日 PIT 未認證。

### 排程改善：每個來源／階層獨立日期進度

每輪按來源 × 三層共 18 列，包含建庫起始／目標結束、2026 年度起始／目標結束、增量巡檢至、下一巡檢日、最早/最新候選日期、日期／檔案證據數、失敗日期、PIT及完整驗收狀態。

**不可跨階層冒用日期**：Bronze 的月度封存不代表已轉成 Silver；Silver 的表可讀不代表 Gold 400+ 指標完成；最新候選日期不等於連續覆蓋。沒有 SHA／血緣證據的資料均不宣稱正式完成。

此表跟隨現有每日上午 09:25／晚間 21:25（台灣時間）更新日期報告的同一個 GitHub Actions 作業；官方資料下載工作排程不變。

## I. 來源排程年份與異常閉環（2026-11-08）

**目前真正連續執行的六條來源下載排程，都是 2026 年增量候選資料搬運。** TWSE/TPEx `v095_2026_price_incremental.py` 由 2026-01-01 到台灣當日；MOPS/TDCC/TAIFEX/NDC `v095_2026_four_source_archive_intake.py` 主要檢查 2026 年現有來源原始檔與異常。獨立 G0 工作流程涵蓋 2000-01-01 至當日的歷史日期和六來源發布規則，並不等於歷史 2000–2026 全量 Bronze/Silver/Gold 已下載／轉換。

**新增錯誤紀錄與重新驗證閉環**：
- 六來源工作或六來源合併重跑若 GitHub workflow 失敗，由 `.github/workflows/v095-source-failure-log-drive.yml` 接收 `workflow_run completed` 的 `failure`，記錄來源、Run ID、失敗 job/step、Git commit SHA 與重驗要求，使用 Drive immutable SHA readback 存到 Operations。這只識別 GitHub job failure；**來源批次內的個別日期失敗，仍需讀原來源 result.json / quarantines，不可被忽略**。
- 失敗後必須先辨識官方原始來源錯誤／格式／授權／時間／Checkpoint 等原因。已驗證成功的不重抓；不安全原始檔保持隔離。排程只可在官方來源或內部邏輯修正、測試通過後復跑。
- 相關下載器、血緣驗證器、錯誤履歷或日期進度程式提交修正後，自動觸發日期報告工作，重新發布來源 × Bronze/Silver/Gold 的日期進度至 Drive；每日台灣 09:25/21:25 仍定時彙整真實 Checkpoint。
- **修復程式不是由 workflow 自動編寫**：自動化可以偵測、分類和保留錯誤、執行既有有界重試、發布報告；對需修改程式才能修正的錯誤，應經過程式調整和測試，不能宣稱 GitHub Actions 會自行理解並修好任何新型錯誤。
- 2026 優先驗收通過後，另以獨立歷史批次工作擴展 2000–2026；必須保存來源最早可得日期，避免興櫃資料混入正式上市上櫃指標。

