# JARVIS R3 G2｜FinMind首兩筆正式PASS 與七來源324 QA總表（2026-11-18）

## 真正執行結果

1. [Run 44277414399](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44277414399) SUCCESS：對3個歷史封存 ZIP 從 manifest 取得 Dataset/股票代碼/data_id/完整月份，FinMind v4 API HTTP200；2000-01股票1604，22筆 native JSON SHA/行列全一致；2022-05股票1264，21筆 SHA/行列全一致；2009-03股票1442財報18筆，17筆完全相同，1筆 `type="-"` 改為 `NetIncomeAttributableToPreCombinationNonCommonControlInterests`，按 origin_name+value 18筆數值相同，但仍不能自動批准別名。
2. [Run 44278523779](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44278523779) SUCCESS：獨立重取2000及2022兩個來源完整 FinMind API JSON，同 frozen ZIP member SHA 和前一 Run SHA 一致；逐筆原生10欄、月份、data_id、主鍵唯一、Bronze SHA核對；正式核准1份 `TaiwanStockPrice` 來源快照公用模板（僅2026-11-18來源版本），對兩份 frozen Bronze 分別核發完整 G2 per-file cert 並 Drive 讀回。
3. [Run 44278824416](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44278824416) SUCCESS：把FinMind兩張新憑證與既有NDC320、TWSE1、TPEx1去重，逐筆和固定74750 frozen file IDs/SHA查核，以新 **隔離 QA Master** 寫入Drive、remote readback成功，沒有覆寫既有322總表。

## 七來源最新來源快照 G2 QA 分布

|來源|G2 verified source-vintage|HOLD / not proven|
|---|---:|---:|
|TWSE|1|12070|
|TPEx|1|13199|
|MOPS|0|1935|
|TDCC|0|40384|
|TAIFEX|0|3140|
|NDC|320|0|
|FinMind|2|3698|
|TOTAL|**324**|**74426**|

注意：320筆NDC是2026修訂快照，TWSE/TPEx及FinMind也是2026重新驗證原件來源版本，不代表各歷史觀察日期同時點的公布版本PIT。不是G3/G4或Silver Ready。

## FinMind 新增真實收據

- 雙月源正式 G2 核准 Master：Drive ID `1hraNEsA-r5JswKyL3SXZffT6xiAfisVr`
- 2000年股價1604 G2 cert：Drive ID `1Yr0FYx5rRtsoDtgAw0aZHKAWdBnsHY0P`
- 2022年股價1264 G2 cert：Drive ID `14aCHaRfHt71f31arMawKc0Jvgy0bAswt`
- native provider original document：Drive ID `12sdROGtg7O3oXFKK9g6gf_Juxntlbw_T`
- independent proof：Drive ID `1VdmwMlHk4tqpwrrkA2CV6GNwqePFthjy`
- 新七來源324 QA Master：Drive ID **`1l6OD1y79u6nNCKK9bPHIfJCopZxeltf6`**，`R3_G2_SEVEN_SOURCE_QA_324_IMMUTABLE_ISOLATED/r3_g2_74750_324_official_source_vintage_qa_master_run_44278824416.json`

## 剩餘待辦不應虛報 PASS

- **FinMind 2009財報**：欄位 `type` 特定舊佔位值與新字串，需要正式版本alias官方佐證；當年的財報PIT發布/更正仍未驗證，維持HOLD。
- **TAIFEX**：期貨10欄、選擇權11欄，2013/2024/2025的表頭/資料列/官方三條註腳已解析；2024年1月25,300行情列原始檔 SHA完整；官方原始歷史CSV表單 POST目前出現ConnectionError，尚未取得與原件整檔可驗證的官方回應，**不能核發正式 G2**。官方FAQ說明某些歷史資料可能需要E-Data Shop授權取得，不能因連線問題判原件錯。
- MOPS/TDCC繼續維持先前原始來源身份/歷史格式與周別證券別等正式證據HOLD。

**安全界線**：上述均為R3 staging隔離QA與Source-vintage G2，Bronze唯讀，不做Silver、Gold，不改舊R1/V3和正式G5 Master。
