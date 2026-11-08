# JARVIS v0.95 六來源官方格式／日期／發布時點比對及差錯修復履歷

建立：2026-11-08。狀態：候選 Bronze 可繼續；G0 完整歷史發布日 **未認證**；Gold PIT **不得放行**。

## 一、判定原則（從官方來源而不是內部檔名推斷）

- 日期分四種：`trade_date`（交易日）、`snapshot_date`／`report_month`（資料歸屬日期）、`published_at`（真正發布時間）、`retrieved_at`（下載時間）。不得相互代替。
- 沒有資料不等於休市；API HTTP 200 不等於回傳資料屬於請求年份；來源未建立前的期間不列缺漏。
- 原始回應保留 SHA256、來源 URL、請求年月、原生格式／編碼、解析版號；由 Bronze 到 Silver 到 Gold 使用原始 file_id + SHA 追溯。
- JARVIS 只分析上市／上櫃；興櫃僅留存。貨幣數值欄於 Silver 換算億元；人數、股數、價格、比率保留原單位。禁止未來資訊偏差。
- `market_dates_2000_2026.csv` 經每來源日曆整理；只有核實正向交易紀錄才標記來源確認交易。未知日期只允許 source probe，不能算失敗率分母。
- 交易日 Gate 是 Bronze 准入，不等於數據架構品質、完整歷史來源、Silver 成功、400+ 指標 Gold 或 PIT 成功。

## 二、六大來源官方／內部資料格式對照

|來源|官方文件及原生格式|既有 v0.95 契約|已確認的格式或日期矛盾|修復與目前限制|
|---|---|---|---|---|
|TWSE|官方 FMTQIK 每日市場成交資訊：日期、成交股數、成交金額、成交筆數、加權指數、漲跌點數；JSON／CSV；[官方說明](https://data.gov.tw/dataset/11672)|8 種來源契約、JSON，以交易日為主鍵|新版 `/rwd/zh/exchangeReport/FMTQIK` 曾回 HTML；舊 `/exchangeReport/FMTQIK` 經實測可取得 2000 年 JSON。市場彙總不等於個股日 OHLCV|查回應 `stat`／欄位／日期年份與 SHA；2000–2026 累積 6,631 個官方正向交易日；2026 現貨休市先用已核實日曆|
|TPEx|[櫃買官方 OpenAPI](https://www.tpex.org.tw/openapi/swagger.json) JSON；歷史個股資料需驗證查詢年月與回應年月|11 種契約，OTC 限上市上櫃範圍；trade_date/security_id 或 index_id|歷史舊網址可能回傳其他月份，取個股日期也不能反推全市場當天所有商品完整|對照 response.date、每列日期、股號、SHA；6,303 個交易日期屬正向證據，休市原因另驗|
|MOPS|[公開資訊觀測站](https://mops.twse.com.tw/mops/web/t21sc03) 月營收舊檔 HTML／CP950，金額常用仟元|2 項月營收契約，`html_cp950`、`NTD1000` → `億元`；report_month/security_id|早期檔名可無 `_0`，新舊字元編碼／頁面標題年月會不同；2000–2004 共 34 筆來源／月份組合未驗證|兩個官方站、兩種檔名、驗證頁面年月與表格筆數；來源可得性未知不得算確定缺漏。仟元轉億元除以 100,000；發布日期不能使用月末或申報期限代替|
|TDCC|[集保官方查詢與說明](https://www.tdcc.com.tw/portal/zh/smWeb/qryStock)：資料日期、證券代號、持股分級、人數、股數、比例；週末營業日持股快照；2008/07 建置，現行歷史查詢保存一年|1 項 `jsonl_legacy_partition`：這是 JARVIS 中介封存，不是官方 CSV／JSON 原生格式；週基準日/證券代號/持股分級|原先僅讀最新 Checkpoint，12 個有來源收據的日期從全歷史管理檔查出；ZIP Manifest 也有 `period+immutable_originals` 與 `month+units` 版本差異|讀取 57 個原歷史管理檔、檢查 SHA；新雙版 Manifest 強制逐檔 SHA、路徑完全吻合。已掃描收據不等於整個週次資料完整，出版日 PIT 未認證|
|TAIFEX|[期交所官方期貨日行情下載](https://www.taifex.com.tw/cht/3/futDailyMarketView)：每日 CSV、年度 ZIP；日下載區間最多一個月；盤後交易日期為交易量歸屬日|16 項 CSV 契約；日期／契約主鍵、各指標原生單位|2015–2017 部分 CSV 行欄位截斷，日期可獨立查驗但數值格式未通過|先以官方 ZIP CRC／SHA、CSV 欄位與日期驗證；年內交易日期 6,633 個正向證據；有截斷者只放行日期不放行行情及 PIT|
|NDC|[官方統計預告發布時間](https://www.stat.gov.tw/News_NoticeCalendar_Content_temp.aspx?MetaI_D=257&n=3717&year=2026)；景氣指標按觀察月份、發布時間另表；修訂歷史 XLSX 常包在 ZIP|1 項 `xlsx` 契約、series/observation_month|目前完整歷史觀察值可能是修訂後版本，不能倒填為當時已公布；2026 舊候選 ZIP 未找到並非官方缺資料|保存官方 ZIP SHA，321 個歷史觀察月份／34 序列；實際初版 `published_at`／歷史 vintage 待查|

## 三、已重現並修正的差錯

1. API 回傳 HTTP 200 卻是 HTML 或錯誤年月：必須檢查 JSON 類型、`stat`、`fields`、`data`、當年當月。
2. 休市／僅結算日期的假缺漏：用 G0 來源交易日曆排除，未知者只調查不當失敗；2026 年未來預定交易日不可當實際成交。
3. 來源日期與公告日期混淆：四日期欄位分離，無證據一律 `PIT:false`。
4. TAIFEX 原生年度 ZIP CSV 截斷：可獨立復原日期；全數值品質不得自動放行。
5. 早期 MOPS 舊檔編碼、檔名與月份：民國年 + CP950；優先只補未驗證月份，不重抓已驗證檔。
6. TDCC 歷史收據只讀游標最新一輪：改掃歷史檔，不憑 Friday 固定推算真實週基準日。
7. TDCC 來源封存 ZIP 多版 Manifest：舊 `month/units` 與 `period/immutable_originals` 雙格式，來源年月與 member path 全數一致且每個 member 必須提供 SHA。
8. TDCC `jsonl_legacy_partition` 內部格式 vs 官方原生 CSV/JSON：必須以原始 HTML/JSON File ID、SHA、`source_record` 和欄位映射做證明；不能單以 JSONL 能讀就判來源合格。
9. 來源 Run 成功但零份下載：分別列出來源已重用、歷史未建檔、無合格 manifest、官方時間未證實、真正 HTTP 失敗；每輪列 blocked reason counts。
10. 定義資料完整率前，先確認來源最早可得日、應有日期、官方是否提供該資料種類。不能用 2000/01 到 2026/12 的全部曆日除原始檔案數。

## 四、來源端與 GitHub 驗收進度

- G0 Run #42454147498：成功，G0 可安全作為資料下載日期前置門檻，不代表 PIT 完整。
- 格式 39 項契約 Run #42455411552：成功，1 類待補強：TDCC 內部 JSONL 與官方原始欄位映射。
- 六來源首批重跑 Run #42455340851：TWSE／TPEx 各新 10 份 B/S/G candidate，血緣 10/10；其他四來源候選 archive 收據按各來源列出。
- 六來源第二批重跑：執行新 Manifest 雙版與來源 SHA 驗證；成功的檔案及舊 Checkpoint 必須不重抓。

### 下載准入的可操作決議

- **ALLOW_BRONZE**：已證明交易日、來源年月與原生格式，可存 Bronze。
- **PROBE_ONLY**：歷史來源/日期未核實，可試抓但不計未下載總數。
- **SKIP_KNOWN_NO_TRADE**：官方確認無交易日。
- **SOURCE_NOT_YET_EXISTING**：來源資料類別當年尚未建立，排除缺漏分母。
- **QUARANTINE_NATIVE_FORMAT**：來源有回應但檔案結構／欄位／SHA 未過，封存錯誤收據且不進 Silver。
- **PIT_BLOCKED**：公告時間／版本未核實，可先整理描述性資料，但不得作當年策略回測。

### 待補清單（尚不可稱完成）

- MOPS 2000–2004 34 筆需進一步查官方歷史來源供應範圍／替代合法封存；
- TDCC 週次完整性與真實公布時間；不能因 47,121 筆原始收據只分布於 12 個週基準日，就假設全部歷史都具備；
- NDC 歷史第一版公布時間及修訂版版本史；
- TAIFEX 2015–2017 完整 CSV 數值欄位修復；
- 26 類發布週期與 39 個資料契約逐資料集的正式 PIT 驗收；
- 2000–2025 源別假日原因與來源資料最早可得年份。

以上問題不阻塞已證實日期的 Bronze 候選下載，但未通過時不得宣稱 Gold PIT 及完整歷史完成。

## 2026-11-08 追加：官方原生資料／歷史封存實測結果（以實際 Run 為準）

1. **MOPS 不是單純月份錯位：** 2026/03 歷史財報封存中發現 `manifest.json` 根節點只有 `numeric_verified,pit_verified,run,units`，沒有 `source/month`；但每個 `units[]` 內有明確 `source=MOPS,month=2026-03`，且分別為 BalanceSheet、IncomeStatement、CashflowStatement。這些是季財報（報表期 2026-03-31），不是月營收，也不能使用該期末代替公布日。修復方案只在全部 units 來源、月份一致且原始成員 SHA 完整時接受為 **候選 Bronze**。Run #42457823238 新增 3 份且本批未阻塞；後續有效性仍須逐批查證。不得把所有曾報錯的 107 份直接認定都合格。
2. **TAIFEX 是報表版型差異：** 官方「期貨價差委託成交概況表」CSV 第一列為標題，第二列為 `交易日期,商品代號,價差委託成交量(B+S),市場總成交量(B+S),價差委託成交比率(%)`，日期 `YYYYMMDD`。原本使用一般期貨日行情第一列即 header 的驗證器，導致 `CSV_DATE_HEADER_MISSING`；新加獨立 title+header+日期+商品+量+百分比比例檢查，禁止放行數值完全認證或 PIT。如果舊檔案放錯月份資料夾，需依**原檔唯一真實交易日**重新驗證正確月份再放候選；不得用資料夾年月代替內容年月。官方清單：https://www.taifex.com.tw/cht/3/futPrevious30DaysSpreadOrdersReport
3. **TDCC 最後一份無 Manifest 舊 ZIP：** 2026/10 封存部分檔案只有 CSV/JSON，沒有 `manifest.json` 或 `complement_manifest_R1.json`，其 JSON 並非可獨立核對原始 SHA、來源月份與路徑的 Manifest。前 3 份具有 `complement_manifest_R1.json` 可透過 per-member SHA 與 source/month 驗證搬運；最後一份繼續 **QUARANTINE**，不應補造 Manifest 或聲稱原始來源已核實。優先改用集保官方週資料重新取得能核對的原始資料；現行官方網站僅保存一年歷史查詢。官方說明：https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
4. **NDC 三筆假缺漏確定來源：** 使用了不適用的 v0.93 月資料夾完整率檢查。官方原始檔是可包含多個歷史觀察月份的 ZIP/XLSX；經 Google Drive 讀回官方 ZIP 與 SHA 對照，原有 321 個觀察月份可用於描述性資料，Run #42457823238 顯示 `blocked=0` 且 `official_observation_months_reused=321`。*初次發布日／歷史修訂版 PIT 仍未證實。*
5. **TWSE、TPEx 延續推進：** Run #42456408655 各新增 10 個價格日 B/S/G 候選，血緣 10/10；不等於 2026 全年完成。所有新增來源應有原檔 SHA、日期回應核對與不使用未來資訊的證據；原始下載斷點正常前進即可，無須因四來源異常而停掉。
6. **歷史錯誤範圍與新排程開關：** 先分清資料集合（MOPS 月營收與季報、TAIFEX 期貨日行情與價差委託日彙總）再呼叫該類型原生解析器。不能把這些不同來源子項目一律算成「來源資料下載失敗」。有來源原始檔但不符當前驗證器者保留原樣與錯誤碼，絕不安插假日期，亦不得放進可回測 Gold。
