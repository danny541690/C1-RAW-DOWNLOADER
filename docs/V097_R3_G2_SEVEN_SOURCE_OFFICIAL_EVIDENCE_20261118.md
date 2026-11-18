# JARVIS R3 G2｜七來源官方資料與歷史格式公開證據（2026-11-18）

## 重要限制

以下網頁由公開來源直接核對，僅能證明「官方來源有相關資料集／制度／欄位」；**不能推論任何保存於 v0.97 的個別檔案就使用同版規格**。沒有官方規格原文快照 SHA、發布時點、原生檔案證據及獨立覆核，即使有來源網址也維持 `CANDIDATE`，不可發 `G2 PASS`。

|來源|已核對的官方/供應商事實|來源網址|仍缺的正式 G2 證據|
|---|---|---|---|
| TWSE | 證交所「每日收盤行情」有 HTML/CSV 查詢；資訊商店 A05 列出證券代號、開高低收、成交股數、成交金額等欄位；A05 不等於所有歷史公開行情 | https://www.twse.com.tw/zh/trading/historical/mi-index.html ; https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8 | 個別 Dataset 起始日期；公用表/商用 A05 版本、生效日及原件綁定 |
| TPEx | 櫃買中心「上櫃股票每日收盤行情（不含定價）」有歷史查詢頁及 CSV 匯出 | https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html | 各 Dataset 最早提供日期、不同年代的欄位/市場範圍、原件版本 |
| MOPS | 交易所說明公開發行公司於2019年第1季起採用 Inline XBRL 財報申報；不能僅用2019年界線取代個別公告與更正日期 | https://www.twse.com.tw/en/listed/xbrl.html ; https://mops.twse.com.tw/ | 個別報表 XBRL taxonomy、公司、發布 PIT 與修訂版次 |
| TDCC | 股權分散表官方明示歷史檔案自2008年7月起建置，現行公開歷史查詢保存期間一年 | https://www.tdcc.com.tw/portal/zh/smWeb/qryStock | 歷史證券分類、16/17級原生版式、封存來源鏈/檔案 SHA |
| TAIFEX | 官方交易制度沿革明示2017年5月15日起開辦盤後交易，不能用整個2017年5月做新舊版本分界 | https://www.taifex.com.tw/cht/4/historyOfTrading | 日盤夜盤欄位和交易日規則、各契約/資料集分別生效日期 |
| NDC | 國發會官方確認景氣指標多次修訂，2024年新制於2024年3月4日發布2024年1月景氣概況時啟用 | https://www.ndc.gov.tw/nc_336_2245 ; https://www.ndc.gov.tw/nc_336_2250 | 各系列歷史起始日、原 Excel cell、公布 PIT／回溯修訂與系列版本 |
| FinMind | FinMind `TaiwanStockPrice` 資料集列有 date、stock_id、Trading_Volume、open/max/min/close 等原始欄位 | https://finmind.github.io/v3/tutor/TaiwanMarket/Technical/ | 供應商版本、生效與修訂紀錄、檔案原生證據；供應商文件不是主管機關證明 |

## G2 正式結構

- 共用規格唯一識別：`source/dataset/historical_era/template_id/native_layout_id`。
- 各模板正式起始日期必須以 `official_dataset_start_date` 為准；僅從 Bronze `source_path` 得到的年月是檔名**候選日期**，不可當作官方起始日期。
- 必要/可選欄位、別名、主鍵、日級生效期間、原始官方文件 Drive ID/SHA、獨立審核記錄 ID/SHA 缺一不可。
- 對每筆原始檔要再附獨立的 `source_data_date`、`source_data_date_verified`、`native_date_evidence_sha256`、Dataset、native layout、來源/檔案 SHA，不能直接猜。
- 共用模板經正式認證後再由 `scripts/v097_r3_g2_shared_74750_reconcile.py` 逐筆處理；只要原生綁定缺證即 HOLD。
- 保留舊版未完成 G2 原件與格式分析履歷，不改 Bronze，不執行 Silver/Gold。

## 目前實際 blocker

凍結七來源母體 `v097_Q0Q4_SOURCE_<SOURCE>_44035354930.json` 的 `records` 欄位**不含** `data_date` 或 Dataset；實際欄位為 `bronze_status, destination_id, evidence_type, historical_profile_status, silver_conversion_executed, silver_input_status, source, source_id, source_path, source_sha256`。

需從已保存的原生格式分析及獨立來源證據生成 `R3_G2_NATIVE_BINDINGS_<SOURCE>.json`，並經驗證後才正式認證逐筆 G2；不能把暫時性來源路徑推定的年月當成已確認的交易/公告日期。
