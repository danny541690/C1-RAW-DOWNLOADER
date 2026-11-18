# JARVIS v0.97 R3｜其他六來源各10筆實檔 G2 原生證據小測試（2026-11-18）

## 實際 GitHub Run 與測試結果

- GitHub [44261840978](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44261840978) **SUCCESS**：六來源各10份真實 frozen Bronze，外層檔案 SHA 60/60 一致、逐檔解析 ZIP成員 CRC/原生 JSON/CSV/HTML、Google Drive 六來源及 QA Master 全部寫入與讀回成功。
- **正式六來源 G2 PASS 0/60，HOLD 60/60**。這是「證據不足無法核准」的正確狀態，程式 SUCCESS 不是 G2 全部 PASS。
- NDC 先前已核准2026修訂版來源快照 G2 **320/320**，未被本次更動，合併七來源歷史正式 G2 仍是 **320/74,750**，非七來源全部小測試達標。

| Source | sample | SHA matched | native inspected | G2 PASS | G2 HOLD | breakdown |
|---|---:|---:|---:|---:|---:|---|
| TWSE |10|10|10|0|10|6 需 dataset-era 官方規格/發布 PIT；4 ZIP其餘 members/歷史規格|
| TPEx |10|10|10|0|10|5 需 dataset-era 官方規格/發布 PIT；5 ZIP其餘 members/歷史規格|
| MOPS |10|10|10|0|10|1 需 dataset-era 官方規格/發布 PIT；9 ZIP其餘 members/歷史規格|
| TDCC |10|10|10|0|10|10 需歷史證券身分/16/17級版本與原生官方規格|
| TAIFEX |10|10|10|0|10|8 需具體資料集官方版式、1 真正為價差委託成交而非期貨OHLCV、1 ZIP展開量超測試上限|
| FinMind |10|10|10|0|10|10 需 API Dataset/schema revision/供應商原件與 PIT，非官網可直接核發的主管機關來源|
| **Total** |**60**|**60**|**60**|**0**|**60**|互不重疊60個原件|

## 具體資料集辨識教訓

- TWSE 凍結 ZIP sample 同時有 `tables/stat/date` JSON 與 `foreign_holdings_2025-01-14.json` 等來源；不可將整個來源當 A05 每日行情。
- TPEx ZIP sample 存在 `valuation_2024-06-20.json` 及 mixed `tables`；不可預設都是個股行情。
- MOPS ZIP sample 的多個成員為 HTML；報表種類、XBRL/IFRS修訂、公告日期不應由 ZIP 檔名判定。
- TDCC 外層 HTML/XML，檔案完整性可以核對，但仍需獨立證明16/17級不同證券類型與周別。
- TAIFEX 8筆 CSV 中實際涵蓋不同 Dataset：`期貨價差委託成交概況表`、選擇權每日行情、大額交易人/未平倉部位。這些不能共用期貨每日行情的主鍵與欄位。
- FinMind ZIP 是原生 JSON + `manifest.json`；例如 `date/stock_id/Trading_Volume/Trading_money/open/max/min/close/spread/Trading_turnover` 或 `date/stock_id/type/value/origin_name`。必須依實際 API Dataset 分流，不能只憑 `source=FinMind` 用官方主站作證。

## 可回溯 QA 收據

Google Drive: `JARVIS_C1_v097_LIFECYCLE/03_DATA_QUALITY/R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED/`

|Source|Drive receipt id|
|---|---|
| TWSE |`1ngYt5ZQ6qkw20ZsTJd5Ks-46qOS_auJF`|
| TPEx |`1G5SKbBwxc6s3_bGFWtyhGacmfGc6YHvm`|
| MOPS |`1ei_0ISn5iJRqtUE5_oyS13JELnxDTVDp`|
| TDCC |`1HhJpkqNMmXICCMo0lq6NeAXBD2EXnbib`|
| TAIFEX |`1MFqouM-NS77srsRub23bXOOCQW4mb3EL`|
| FinMind |`1ShSMExdKQYd2r2mOgKvBdmQ9dIU7gQAt`|
| Overall Master |`16zg2Qe1IuxqdXeRd1c-ztTypXlxiKf00`|

## 正式核准條件仍缺

NDC 的成功案例具備官方原始 XLSX `ws.ndc.gov.tw` 即時重取等 SHA、各月原始儲存格對照與獨立 reviewer/Drive readback。對其他六來源，下一步**必須**從歷史下載紀錄反查每筆的原始官方網址和原件 bytes/SHA；按真實 Dataset/版本建立特定來源原生模板，以各一小組可完整證明的樣本取得真實 G2 PASS。不能因60/60 SHA相符或 ZIP CRC 正確就發 G2 PASS。

本次完全不改既有 NDC 核准登錄，不動 Bronze／Silver／Gold，不切 R1/V3 和 G5 Master。
