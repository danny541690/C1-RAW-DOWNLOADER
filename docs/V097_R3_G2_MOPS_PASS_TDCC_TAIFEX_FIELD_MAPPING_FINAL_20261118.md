# JARVIS v0.97 R3 G2｜MOPS首筆PASS、TDCC列映射釐清、TAIFEX官方歷史來源HOLD（2026-11-18）

## 驗收 Run 與結果

- [44282067824](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44282067824) SUCCESS：MOPS、TDCC、TAIFEX 3來源×10 frozen Bronze source SHA/原生欄位、表頭、內容分布及Google Drive讀回。
- [44282355777](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44282355777) SUCCESS：MOPS 2025-02 OTC德麥1264完整11欄財報資料與官網重取相同；TDCC 2026-10-08 2365官方傳統HTML查詢返回589位元組佔位頁，不是原始股權表。
- [44284071346](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44284071346) SUCCESS：MOPS全58張表官方2026版本與frozen 2025來源比較。原件857家公司，目前官網861；4個2026才初上櫃的 2249/6825/6898/6938 不得回填入2025；另3489森寶→長耀地產、6474華豫寧→維夫拉克控股屬2026更名，**857家公司數值欄都相同**，不是營收金額遭毀損。
- [44284887357](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44284887357) SUCCESS：核對TWSE官方2026初上櫃公告、MOPS 2025原件及官網現行同一月份數值：用歷史上市櫃身分與公司名稱的受限別名，核准1份 `MONTHLY_REVENUE` 子模板、發行 **MOPS正式G2來源快照憑證1張**，Drive遠端讀回PASS。
- [44285197374](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44285197374) SUCCESS：把MOPS1加入舊的NDC320+TWSE1+TPEx1+FinMind2，新R3隔離 QA **325/74750 PASS、74425 HOLD**，舊324檔案保持不可變。
- [44283350941](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44283350941) SUCCESS：TDCC 10份真實HTML均「15級+第16列合計」，核實各級戶數/股數相加與合計相等，比例四捨五入誤差小於0.2百分點，原件SHA相同。
- [44285828754](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44285828754) SUCCESS：實際下載TDCC官方 `openapi.tdcc.com.tw/v1/opendata/1-5` 9.9MB、70125資料列，股票2365於2026-11-13有17列：1–15級有資料，第16級 **0人/0股/0.00%**，第17級為 **合計97871戶/221528496股/100%**。與Frozen 2026-10-08的15級+第16列合計98198戶/221528496股，**兩份日期不同不可逐值比較**；API `\ufeff資料日期` 有BOM需去除，`證券代號` 可能帶尾端空白須保留原值但標準化索引。

## 三來源格式子模板表

|來源與Dataset|原生表頭/期間/內容|校正的本質錯誤|有效處理|
|---|---|---|---|
|MOPS OTC MonthlyRevenue 2025-02|11欄，58表，857家，源檔百萬元? **實際原件標示千元**|當前官網回填2026初上櫃4家、2026更名2家；不是2025營收數字變更|市場身份 PIT 過濾4家公司、公司名稱同一公司代碼的期間化別名；保持857家及原始千元、不改Bronze；已限縮至2026再驗證來源版本核發1筆G2|
|TDCC SHAREHOLDING 2026-10-08 HTML|5欄，序號1–15級，序號16合計；98,198戶/221,528,496股/100%；15級比率加總99.95%|先前將序號16「合計」誤當第16級；現行OpenAPI含第16級零值且序號17合計；兩種封裝不能直接比列數|分 source native_layout：`HTML_15_PLUS_TOTAL16` vs `OPENAPI_16_PLUS_TOTAL17`。以明確 `tier_code`及`is_total`標記，比對同週/同證券/同持股級距，不跨週推定數值一致|
|TAIFEX LARGE_TRADER_FUTURES|原生10欄，2013-08 19,194筆；2024-01 25,300筆|和選擇權11欄、期貨價差成交、組合委託、法人部位混為同模板，特殊值「-」與footer解釋不全|按Dataset多模板，保留尾註、日期/口徑版次，官方historical CSV原件需真正重取，現在POST連線失敗，仍HOLD|
|TAIFEX LARGE_TRADER_OPTIONS|原生11欄，2025-05 8,400筆，包含買賣權欄|不能當10欄期貨歷史格式改版|獨立11欄格式及主鍵含call/put，原件SHA與官方整月行列仍需對照|
|TAIFEX其他|組合式成交4欄、單式/商品委託8/9欄、法人期貨未平倉15欄等|不同報表有不同date、header與空尾欄，不是大額交易人格式損毀|按真實報表類別分類，再由正式原生資料、單位、有效期間核准|

### MOPS 真實修復證據

官方月營收 URL：`https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_114_2_0.html`；TWSE官方2026初上櫃公告 `https://www.twse.com.tw/announcement/auction?response=html&yy=2026` 及 `https://www.twse.com.tw/announcement/publicForm?response=html&yy=2026`。原件2025-02公司1264德麥：當月營收412565千元、上月681442千元、去年同月342042千元、MoM -39.45%、YoY +20.61%、當年累計1094007千元、去年累計1022510千元、累計YoY 6.99%，與官網逐欄相同。

公司名與證券交易身分為 **effective-dated dimensions**：因2026更名／初上櫃，不可回填成2025年的投資回測選股母體。這次一份source-vintage格式的正式G2 PASS仍只說明2026-11-18可重驗來源內容，不能當作2025當時已公開的原始發布 PIT證明。

### TDCC 真實欄位映射

HTML：`序,持股/單位數分級,人數,股數/單位數,占集保庫存數比例 (%)`。
OpenAPI：`證券代號,占集保庫存數比例%,人數,\ufeff資料日期,股數,持股分級`。

**HTML 2026/10/08 stock2365**：15個級距、seq16「合計」98,198人、221,528,496股；15級比率總計99.95%，合計100%。**OpenAPI 2026/11/13 stock2365**：tier16記0人、0股、0%；tier17合計97,871人、221,528,496股、100%。兩份原始數值不同屬不同時點，不能將2026-11-13 API資料當作2026-10-08官方原件。現行API未提供與這份凍結HTML同一週別的正式回應證據，故 TDCC G2 HOLD。

## Google Drive存證與狀態

- 最新**七來源325 QA Master**：`1zi603mMo-6GQQOrZxArvjdvzQfqYdfp8`
- **MOPS 第一筆正式 G2 certificate**：`11EGW0t8QhnJex8YJa3yudP4Zshx394Cn`
- MOPS正式核准模板及原件綁定：`1z4HDCfB4ZREqnsNGlfn3bJKSaPdkiYJc`
- MOPS 官方來源/改名/4家IPO review：`1oBzDccIZ9QozW_mq0gfljpTwrKnPZHZF`
- MOPS 實際4新增/2更名欄位逐值：`1BsxEUYV3inNkMajUokjUINmjuwmYOOxM`
- TDCC 10份15級總帳驗證：`1k-hVuOm7iAqBKflYyg9L94FVqhTauDaX`
- TDCC 官方OpenAPI 17列證據：`19F-qV-6khKVcSk6aBwzrPyVVXYmumJRE`
- TAIFEX 10份 native 列數與格式指紋：`19_uAJgvVCxSJu-bXRnjjhyVrxmR6-Nmw`
- 最初30份來源 SHA與結構 QA Master：`1ZdsFpd7ZghwpHabRxu_JKUjastkw2GOH`

**安全**：MOPS1是R3 staging 隔離正式source-vintage G2憑證；舊G5 master與R1/V3不變，Bronze唯讀，不做Silver/Gold。TDCC、TAIFEX不能強行PASS，需同週官方原始快照及歷史CSV官方回應。
