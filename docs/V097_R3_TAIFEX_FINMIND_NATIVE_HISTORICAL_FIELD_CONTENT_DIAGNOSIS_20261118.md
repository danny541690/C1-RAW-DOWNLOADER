# JARVIS R3 G2｜TAIFEX / FinMind 真實原件、歷史格式及來源 API 深度對帳（2026-11-18）

## 實際來源與不可變驗收結果

- 本報告使用 Drive 真實 Bronze 原件與 GitHub Actions 實測，不依檔名推測每檔格式。
- TAIFEX：2013-08、2024-01 期貨大額交易人 CSV；2025-05 選擇權大額交易人 CSV，透過 Drive 原件 ID 讀出內容；期貨10欄，選擇權11欄。三份原始 SHA 與 frozen manifest 一致。
- FinMind：封存 ZIP 的 `manifest.json` 與單一 `*.raw` 實體 JSON；2000-01個股價格、2009-03財務報表、2022-05個股價格。下載 API v4 必須重現 `dataset`、`data_id` 股票代碼、完整月份 `start_date`/`end_date`。不帶 `data_id` 的先前測試 HTTP 400 不可宣稱資料損毀。
- FinMind 正確API重放 GitHub [44277031863](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44277031863)：2000 price 22/22 rows *逐欄完全相同且原生 response bytes SHA 一致*；2022 price 21/21 rows 亦逐欄及 bytes SHA 相同。2009 財報18/18筆，唯一資料欄 type 字串改名（數值及中文 origin_name 完全相同），故原始 bytes SHA 不一致。
- FinMind 別名補查 GitHub [44277414399](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44277414399)：2009/03/31 股票1442、中文欄名「合併前非屬共同控制股權損益」，舊2009封存 `type="-",value=0.0`，新版回應 `type="NetIncomeAttributableToPreCombinationNonCommonControlInterests",value=0.0`；按 `date+stock_id+origin_name` 比對，全部18個項目 value 相同，但這仍是 *候選欄位別名*，尚未正式獨立證明當年欄位發布版次。
- TAIFEX 最新真實官方源 CSV 回放 [44274879527](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44274879527)：指定歷史日期的 POST 遇到 ConnectionError，不能與2024年1月25,300行原件比對；測試收據已 Drive 讀回；不是 Bronze 毀損，尚無 TAIFEX source-vintage G2 PASS。
- TAIFEX 即時 OpenAPI [44273601714](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44273601714)：大額交易人期貨 JSON 回傳 HTTP200、1410列、欄位 `Date,Contract,ContractName,SettlementMonth,TypeOfTraders,Top5Buy,Top5Sell,Top10Buy,Top10Sell,OIOfMarket`；但不是2024歷史原始整月CSV，不能只看相似欄名核准歷史 G2。

## 實際 TAIFEX 日期與欄位分布

|來源封存|native type|欄位|實際資料列|交易日|日期最早至最晚|商品代碼|官方註腳|
|---|---|---:|---:|---:|---|---:|---:|
|2013-08|futures large trader|10|19,194|21|2013/08/01–08/30|232|3|
|2024-01|futures large trader|10|25,300|22|2024/01/02–01/31|287|3|
|2025-05|options large trader|11|8,400|20|2025/05/02–05/29|52|3|

期貨原生10欄依序：`日期,商品(契約),商品名稱(契約名稱),到期月份(週別),交易人類別,前五大交易人買方,前五大交易人賣方,前十大交易人買方,前十大交易人賣方,全市場未沖銷部位數`。

選擇權原生11欄：在商品名稱之後另有 `買賣權`，其餘欄位後移。不能誤視為同一 Dataset 歷史改版。期貨2013/2024的同10欄可建立「欄位相容的候選公用模板」，但不能直接推定2000–2026期間全不改版。

2013年期貨CSV有50個純 `-` 的數值欄，並且2013/08/14–20出現TX、到期月份/交易人類別 `-` 的5組重複 placeholder（全10欄相同）；依官方註腳「-」代表當日無掛牌週契約，不能把它當0或普通主鍵衝突；2013年為正式 PRIMARY KEY 設定 `null/no_contract` 及原始 row ordinal。2024期貨25,300有效資料列的交易人類別0/1各12,650行，2025選擇權8,400行的交易人類別0/1各4,200行。所有樣本均帶3行原生註腳，必須與資料列分離但不丟棄。

### 期交所官方文獻的語義

官網大額交易人資料（期貨／選擇權）包含0/1交易人類別、到期月份 666666/999999 aggregate，`-` 不等於0。TAIFEX 官方文獻稱2008-12-17以後到期結算日對即將到期合約部位計算有差異，2022-11-09起某些TX週到期揭露範圍有新說明，這些是**統計口徑與Dataset歷史版本證據需求**，不可只用同樣的10欄視為全歷史同口徑。官方URL `https://www.taifex.com.tw/enl/eng3/largeTraderFutQry`。

## 實際 FinMind 三個歷史時期

|封存資料|Dataset|股票|原件/重新GET行數|原件欄位|API 結果|byte SHA match|
|---|---|---|---|---:|---|---|
|2000-01|TaiwanStockPrice|1604|22/22|10|HTTP200, all rows identical|TRUE|
|2009-03|TaiwanStockFinancialStatements|1442|18/18|5|HTTP200, 17 native keys same, 1 type alias change, origin_name/value all18 match|FALSE|
|2022-05|TaiwanStockPrice|1264|21/21|10|HTTP200, all rows identical|TRUE|

2000年股價原件第一列：`2000-01-04,1604,1308000,15637400,12.0,12.2,11.7,12.0,0.3,292`；
2022年股價原件第一列：`2022-05-03,1264,5902,1619586,275.0,275.0,273.5,273.5,-2.0,201`。
2009年損益表原件欄位：`date,stock_id,type,value,origin_name`；日股價為 `date,stock_id,Trading_Volume,Trading_money,open,max,min,close,spread,Trading_turnover`。兩個 Dataset 不得共用 native format field contract。

正確 API GET：
`https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=1604&start_date=2000-01-01&end_date=2000-01-31`
`https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockFinancialStatements&data_id=1442&start_date=2009-03-01&end_date=2009-03-31`
`https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=1264&start_date=2022-05-01&end_date=2022-05-31`

FinMind 2026 public docs: https://finmind.github.io/quickstart/ and https://finmind.github.io/tutor/TaiwanMarket/Technical/ and https://finmind.github.io/tutor/TaiwanMarket/Fundamental/ . FinMind 2026 changelog includes schema/coverage changes (e.g. 2026-05-19 includes emerging financial reports, 2026-05-22 revenue create_time), so data observation year and provider return schema-vintage MUST be tracked separately. For JARVIS only TWSE/TPEx listed securities are in scope. Published now ≠ published in 2000/2009/2022; historical PIT remains HOLD unless evidenced.

## 修復建議

### TAIFEX
1. 先從官方 download form HTML/JS 抓取**真正 action、method、CSRF/session/form body**；歷史 `largeTraderFutDown`、`dlLargeTraderFutDown` 命名不可以猜測。歷史 POST 連線失敗時紀錄 request route/header status、DNS/TLS/timeout，不要判 Bronze 壞。
2. CSV CP950/Big5 decode，不准 `errors=ignore`；使用 full CSV parser 將 native header、date rows、3 footer notes 分開存。
3. Dataset family 分為期貨大額交易人10欄、選擇權大額交易人11欄、價差委託、每日行情等；兩張前者 native_pk 必含 observation day/product/expiration/type，選擇權另有 call/put。2013 的 `-` placeholder 不可強迫一般主鍵唯一，按 native row ordinal + semantic special key 留證據。
4. 依2008-12-17、2022-11-09及商品/成交時段資料口徑建立候選 period，待官方文獻與實際對應表核准；同欄不代表同口徑。
5. 對2008/2013/2024/2025每種類別各5–10份原件做 row-level diff、官方原件/回傳 SHA、版本/發布 PIT，再核發一種真正G2 PASS。對無法取得的舊版保留HOLD。

### FinMind
1. API v4 requests 必須帶封存 manifest 的`dataset`,`stock_id→data_id`,完整月份 start_date/end_date；合法token存在 GitHub Secrets `FINMIND_TOKEN` 時以Bearer傳入，**不能印token**；不要以單日查詢代替月檔。
2. 建至少三種非歷史認證的 Dataset 子規格：price10、financial5、institutional5，`TaiwanStockPrice` 與 `TaiwanStockFinancialStatements` 分離；按 provider **response asof** 另外記版本。
3. 2009`type=-` 對 `NetIncomeAttributableToPreCombinationNonCommonControlInterests` 只建立一筆候選alias，條件是 date/stock_id/origin_name/value 及官方 docs 兩方確認；保留 raw 原值。2009財報的資料觀察日期不等於實際公告日期，財報PIT需查MOPS公告日期與修訂時間。
4. 已證實2000/2022完整JSON bytes SHA與目前 API 相同，可優先建立**2026來源快照限定**的獨立正式 template/逐筆證據，不可推回2000或2022年已知；由第二個獨立Run確認原件SHA、原生date/stock_id、有效字段和 remote response SHA，Drive遠端讀回後再核發G2。
5. 只有核准格式且真實檔案逐筆綁定才列G2 PASS；否則 HOLD；不要由本輪程序success算過關。

## 對帳及 Drive 真實證據 ID

- TAIFEX native 10: `1i-DwJiVkKw1BqZ5UbK4tIDI9Njd-n2uw`; historical POST ConnectionError：`1JB0SQeUNEnI-Nnju-1wcV0-zaV9B62-F`；current-only OpenAPI：`1tkKWW7S-El3hjfr9x_3pjNmpbW6btoaX`。
- FinMind frozen native 10: `1MeJ6FbsDly-dyhesnZl0dJnRdLdRrT8t`；2000重放 `1LRm9FgatXKZmQ6ncX39Jc1W_uj1j-ceL`、2009 alias `1IVZ_FNEbFetgTJF9VLMKB2LI-EGApXJz`、2022重放 `1vO0CkCgK4qoR_CQCMFzuIv3VDrsf2YgV`。
- **FinMind 3-vintage master**：`1Nk8QSrLJri6kCU-MUhMyVCFFLM7WWbbz`，Run `44277414399` SUCCESS、remote readback。
- 最新七來源原有已核准QA來源快照322筆（NDC 320、TWSE 1、TPEx 1），以上兩來源尚未新增正式G2憑證；不覆寫 G5、Bronze 唯讀、無 Silver/Gold。
