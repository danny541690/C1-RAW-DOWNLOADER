# JARVIS R3 G2｜四個未核准來源真實首例核證（2026-11-18）

## 已正式上線執行，注意 PASS 不可虛報

- [Run 44272770584](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44272770584)：4來源各10筆完成原生讀取與 SHA、4來源證據收據寫入/讀回，但主總表因 Python tuple 不等於 Drive JSON list，最後一步 **FAILED**。此為程式序列化問題，非 Bronze 損毀。
- [Run 44273111255](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44273111255)：修復後 **SUCCESS**；MOPS、TDCC、TAIFEX、FinMind 各10筆真實 frozen Bronze，官方文件 GET + SHA、外層資料 SHA、ZIP members CRC／原生 CSV/JSON/HTML 欄位判定、逐來源證據報告與 Master 都已確實上傳 Google Drive 並遠端讀回。
- [Run 44273601714](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44273601714)：**SUCCESS**；期交所 `https://openapi.taifex.com.tw/v1/OpenInterestOfLargeTradersFutures` GET 200，回傳 JSON 1410列及正確 `Date,Contract,ContractName,SettlementMonth,TypeOfTraders,Top5Buy,Top5Sell,Top10Buy,Top10Sell,OIOfMarket`；但未與2024-01-02封存 CSV 的原始 bytes 完全匹配，故只能認定資料集/欄位候選，非歷史來源 G2 PASS。FinMind `https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&start_date=2022-05-03&end_date=2022-05-03` 返回 HTTP 400，無可用的原始回應 bytes / token 驗證證據，維持 HOLD，不能冒稱檔案損毀。

## 四來源實測真實結果

|來源|實測 frozen 資料|官方參考文件取得+hash|原生表頭與官方或供應商欄位候選吻合|正式 G2 PASS|HOLD|
|---|---:|---:|---:|---:|---:|
|MOPS|10|2|0|0|10|
|TDCC|10|2|0|0|10|
|TAIFEX|10|2|3|0|10|
|FinMind|10|2|3|0|10|
|**合計**|**40**|**8**|**6**|**0**|**40**|

**七來源 G2 真正已核證來源快照依舊是322筆，NDC 320、TWSE 1、TPEx 1，尚有74428筆需要歷史規格與來源 identity 證據。** 四來源40筆測試成功並非正式 G2 PASS；不能算七來源全過，更不能執行 G3/G4 的 release 或 Silver/Gold。

## 各來源明確缺失與下一輪有效動作

1. **MOPS**：封存 ZIP 中找到 `https://mopsfin.twse.com.tw/compare/report`；但缺可重現的 GET/POST 查詢表單參數、實際財報（公司、季別、報表種類、編修版號）、官方公開/更正 PIT，以及確切原始 HTML response SHA。下一輪應由封存 manifest 或已保存的下載 log 還原查詢 payload 與原始 response，不能拿財務比較首頁當作原件。
2. **TDCC**：凍結10筆外層 HTML/XML SHA 正常，官方股權分散表頁有說明，但缺每週日期、當時證券身分類別、16或17級原生級距與可證實的官方來源檔或開放資料下載 response。先以同一張表的周別、有效證券別與 native tiers 做完整原生 parser／歷史版本選擇，再拿官方該周原件比對。
3. **TAIFEX**：已用官方開放資料 PDF 與實際 CSV 確認3筆表頭候選；本輪近年開放 API 直接回應的是目前資料，並非與封存2024-01-02 CSV 完全一致的2024年原件。下一輪應對官方 `/cht/3/dlLargeTraderFutView` 使用該日期起迄歷史下載表單，核對完整 CSV 行列與交易時段、格式版次，再以來源快照 PIT 上鎖正式核准。不能把選擇權、價差或大額交易人的表頭合併成一版。
4. **FinMind**：至少3筆 `TaiwanStockPrice` 字段吻合文檔。2022年資料重試無授權出現400，需合法的可用 API 認證和與封存 file_id/data_id/start/end 完全相同的查詢，驗證全量回應行數、欄位、每筆值和 source vintage。FinMind 是供應商，不可冒稱交易所官方原始資料。

## Google Drive 實際完整證據收據

資料夾 `JARVIS_C1_v097_LIFECYCLE/03_DATA_QUALITY/R3_G2_FOUR_SOURCE_FIRST_PASS_CERTIFICATION_PILOT_ISOLATED/`

- MOPS 10 real receipt：`1Z5G0MCGuEX11fLk62Tls1qmklw1vMZGV`（前次Run），本次成功Run：`14dwObMBEkqkXi8rHZYkIeUfqsJwP896G`。
- TDCC：`1Rce4zNgomSXVhV576ZpxAsNfYJXinVUZ`。
- TAIFEX：`1i-DwJiVkKw1BqZ5UbK4tIDI9Njd-n2uw`。
- FinMind：`1MeJ6FbsDly-dyhesnZl0dJnRdLdRrT8t`。
- **40筆四來源正式核證嘗試主總表**：`r3_g2_four_source_first_formal_master_run_44273111255.json`，Drive ID **`1dKqBRATK_yj93kf-hE-vHNmM1cmW4Hod`**。
- 期交所官方 API/FinMind 來源回應比對收據：`R3_G2_FOUR_SOURCE_ENDPOINT_ORIGINAL_PROOF_ISOLATED`，Master `r3_g2_original_endpoint_master_run_44273601714.json`，Drive ID **`1MPiflUN-SCVLVf8zt323VVTNafQT6dTb`**。
- 各來源原生證據與四來源 Master 都已 Google Drive 實際遠端讀回。

既有七來源版本模板、143項候選格式與 prior 19 runs 的完整永久索引仍在 `03_DATA_QUALITY/R3_G2_SEVEN_SOURCE_TEMPLATE_PERMANENT_HISTORY`，Master Drive ID `1fHa1s6rOMK2NrLj0AaN1cmRitaBczEgJ`。本輪新報告獨立保存並連結，尚未覆寫 prior Master，未修改 Bronze、不執行 Silver/Gold。
