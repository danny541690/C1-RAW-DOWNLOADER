# JARVIS R3 G2｜MOPS、TDCC、TAIFEX 真實欄位／內容／官方格式交叉診斷（2026-11-18）

## 完成的真實測試與範圍

- [GitHub Run 44282067824](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44282067824) SUCCESS：MOPS、TDCC、TAIFEX 共30筆真實 frozen Bronze，全部原件 outer SHA 相符，對 MOPS HTML 表格、TDCC HTML 股權級距、TAIFEX CSV 每個原生欄位與日期分佈進行抽樣分析；報告與 Master Google Drive 完整讀回。
- [Run 44282355777](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44282355777) SUCCESS：MOPS 2025-02 上櫃月營收股票1264的完整11欄與實際官方歷史 HTML API 回傳全值吻合；TDCC 2026-10-08 股票2365 官方 POST 回傳的是 HTTP200 589B 非資料表（不可誤稱官方原件核准）。
- [Run 44282907695](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44282907695) SUCCESS：完整 MOPS 官方 HTML 58表 vs frozen ZIP原件58表，逐公司資料比對顯示**857 frozen vs 861 現行官網**，新增證券代碼 **6938、6825、6898、2249**，另 **6474、3489** 整列數值不一致；原件公司1264完全吻合；全報表 **不得**授予G2。四筆新增可能是事後補申報、兩筆可能是更正，須查申報履歷，不能憑這個差異直接宣告其原因為何。
- [Run 44283350941](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44283350941) SUCCESS：TDCC 10真實 frozen HTML **10/10** 完成15分級+第16列「合計」、人數／股數相加等於合計、分級比率允許分別四捨五入誤差；官方 `https://openapi.tdcc.com.tw/v1/opendata/1-5` HTTP200但 >5MB guard，因此沒有完成同一股票/週別官方原件值對照，G2仍HOLD。
- 此次新增 G2 0。已核准來源版本 QA仍為 NDC320+TWSE1+TPEx1+FinMind2=324/74750，HOLD74426。**程式 Run SUCCESS只意味測試正常，不能當正式 G2 通過。**

## 三來源真正的 schema/content 差異

|來源|資料實體|原生欄位、列數、值|官方參考及衝突|明確修復|
|---|---|---|---|---|
|MOPS|1份 frozen ZIP 2025-02 OTC t21sc03 HTML、1份 manifest|58表，857不同公司，11欄月營收，股票1264 德麥：當月412565千元、上月681442千元、去年同月342042千元、MoM -39.45%、YoY 20.61%、累計1094007千元、去年累計1022510千元、累計YoY6.99%|官方現在的同月報表58表、861公司；4新增、2既有欄位整列不同；整份bytes SHA亦不同|原件來源版本 `capture_asof` 與申報／更正版次分開；保留舊值；對官方修訂 diff 清冊逐公司輸出，再依當時官方回應或下載履歷證明 frozen版本，絕不自動補新四檔|
|TDCC|10份 frozen HTML各一週一證券|每份表頭5欄：序、持股/單位數分級、人數、股數/單位數、占集保庫存數比例；**15個級距＋第16列合計**，不是16個級距|官方表以每週最後營業日、按證券歸戶持股級距；歷史2008-07起建，官方開放資料版 `1-5` 很大，當前HTML POST回應不是可驗證原件|解析15+total、shareholder/share總和核實、ratio rounding `abs(sum-100) <=0.2`；不得把合計 row 計入級距。使用股票 ID 有效期間、週別及官方當時原始 response才核發G2|
|TAIFEX|10份真實 CSV/ZIP 等原件|2份大額期貨10欄（2013/08 19194行、2024/01 25300行）；1份大額選擇權11欄（2025/05 8400行）；另6份其他商品報表及1份ZIP尺寸保護|期貨10與選擇權11不是年份改版，而是不同 Dataset。期交所官方 opendata format 文件和實際報表需按商品版本判定；前次官方歷史 POST ConnectionError|按 Dataset 設子模板：大額期貨、選擇權、價差成交、個別/組合委託、法人未平倉、每日行情；CSV表頭/日期格式/尾註/交易時段/單位各自解析；歷史官方CSV bytes/所有 rows重查才可發G2|

## MOPS 真實11欄樣本（2025-02上櫃德麥1264）

|欄位|frozen原件|現行官方|
|---|---:|---:|
|公司代碼|1264|1264|
|公司名稱|德麥|德麥|
|當月營收（千元）|412,565|412,565|
|上月營收（千元）|681,442|681,442|
|去年當月營收（千元）|342,042|342,042|
|上月比較增減%|-39.45|-39.45|
|去年同月增減%|20.61|20.61|
|當月累計營收（千元）|1,094,007|1,094,007|
|去年累計營收（千元）|1,022,510|1,022,510|
|前期比較增減%|6.99|6.99|
|備註|-|-|

**嚴禁把原件「月營收千元」當成使用者指定的「億元」**：轉換需明示除100000（1億元=100000千元），G2僅保留原始單位，不做Silver變換。

## TDCC 2026-10-08/2365 完整數值示例

凍結原件的15級別戶數加總 **98198**、股數加總 **221528496**、比率加總 **99.95%**。原始第16列 `合 計` 記載 **98198戶、221528496股、100.00%**；0.05百分點是原件各分級百分比的逐級捨入造成，既不是資料錯誤也不是額外16級。正式主鍵至少含 source-issued security id、week end、native tier ordinal；級距欄不得硬套全歷史相同級距；不區分上市/上櫃/ETF及歷史代碼就不能核准整批TDCC。

對2025年檔案，HTML表單可包含2026年下拉週別，這只是**抓取時的頁面UI**，不能推定是該2025週資料的發布日；歷史PIT必須在正式證據中分開證明。此問題不可拿來判文件本身毀損。

## TAIFEX 2024-01期貨大額交易人10欄

`日期、商品(契約)、商品名稱(契約名稱)、到期月份(週別)、交易人類別、前五大交易人買方、前五大交易人賣方、前十大交易人買方、前十大交易人賣方、全市場未沖銷部位數`。

2024/01/02的原件 BRF 202403 trader type0: `89,103,97,103,103`；type1: `40,0,40,0,103`。兩者不是同一列重複；2013年的 `-` 字段另須按官方原生註腳判作不可用／未掛牌情況，不能填0。期貨2013和2024表頭同10欄，仍需確認個別統計口徑及最後結算日的歷史制度變更。2025年選擇權第4欄新增`買賣權`，11欄不同契約。

TAIFEX樣本還出現 `2017-09` 單式委託表頭8欄、實際資料列9欄，`2024-11`各商品成交表頭9欄、資料列10欄，這是尾部空欄／CSV格式差異候選，應先檢查最後空白欄及 quotation 再判異常，絕不可強制套大額10欄模板。1個2026 ZIP 因尺寸保護暫未深讀，列為資源HOLD而非毀損。

## 具體最短修復順序

1. **MOPS：** 已用真實官方歷史 URL 核對全體，優先查 6938/6825/6898/2249 的上市日期與2025-02補申報、6474/3489的更正公告，找出有效時點及封存版本官方證明。可建立受控 `source_publication_vintage`，但在完整版本佐證前不得硬核發G2。
2. **TDCC：** 先接受已實證的15級＋合計 schema/數值自洽作內部Native Gate，不要因2013–2026混用16/17級誤判。利用官方OpenAPI `/v1/opendata/1-5` 以stream/pagination/分檔過濾確認某1期某股票與原始HTML的15級數值與週別一致，對照有效證券別；若僅提供最新資料不可反向宣告歷史已核准。
3. **TAIFEX：** 現有表頭合法、欄數分組與內容已解析，阻擋是官方歷史原件下載回傳ConnectionError。重新分析正式表單action/CSRF/session、GET/POST與市場下載服務提供日期範圍；官方歷史備份/e-DataShop如需授權則不可以用目前OpenAPI代替。首先選1份可重取全月大額交易人CSV，再自動擴展同資料集。

## 真實可追蹤 Google Drive 原件與QA

- 30筆三來源Native Master：`1ZdsFpd7ZghwpHabRxu_JKUjastkw2GOH`。
- MOPS 全58表、857 vs861與4新增2修訂差異：`1_OwT9qEhd2AZtILmO1yCa2zGABMCNZ4M`。
- TDCC 10份15分級合計自洽：`1k-hVuOm7iAqBKflYyg9L94FVqhTauDaX`。
- MOPS/TDCC官方路由與源資料測試Master：`1gsrV7G-7aBN5hUhdPYX5pkxhIGcZcAfw`。
- TAIFEX 深度10筆收據：`19_uAJgvVCxSJu-bXRnjjhyVrxmR6-Nmw`。
- 既有七來源324已驗證source-vintage QA Master：`1l6OD1y79u6nNCKK9bPHIfJCopZxeltf6`（本輪不覆寫）。
- 全部 QA 操作留在 `JARVIS_C1_v097_LIFECYCLE/03_DATA_QUALITY/` R3隔離資料夾。既有R3 historical templates和 G2 source contract 本輪不當作正式實證修改。Bronze唯讀；未執行Silver/Gold或切換生產G5。
