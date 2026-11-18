# JARVIS v0.97 R3｜七來源 G2 共用模板重構實測總報告（2026-11-18）

## 本次真實執行

- **Run 44250976481**：G2 共用契約比對引擎，對照74,750份凍結來源檔案逐筆產生可追溯 HOLD/PASS 狀態；七來源各自保存不可變 QA 收據，最後 Master 已寫 Google Drive 並獨立讀回，SUCCESS。
- **Run 44251222513**：七來源真實凍結 manifest date-field 稽核，SUCCESS。所有來源的 baseline `records` 結構**均無** `data_date`／`date`／`year`／`month`／Dataset，只有 `source_path` 可能含年月文字。
- **Run 44251486666**：修正 G2 必須使用獨立核證的 `native_binding.source_data_date` 而不是從 baseline 猜日期後，重新執行全量74,750筆逐筆稽核，SUCCESS。
- **Run 44251892156**：七來源各10筆真實 Bronze 目的檔（共70筆）SHA及原生格式候選蒐證，SUCCESS；七份收據及 Master 均成功寫入 Drive 並讀回。

GitHub Actions：
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44251486666
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44251222513
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44251892156

## 正式 G2 進度

| 資料來源 | 固定母體 | 正式 G2 PASS | HOLD | 凍結 manifest 原生日期欄 |
|---|---:|---:|---:|---|
| TWSE | 12,071 | 0 | 12,071 | 無 |
| TPEx | 13,200 | 0 | 13,200 | 無 |
| MOPS | 1,935 | 0 | 1,935 | 無 |
| TDCC | 40,384 | 0 | 40,384 | 無 |
| TAIFEX | 3,140 | 0 | 3,140 | 無 |
| NDC | 320 | 0 | 320 | 無 |
| FinMind | 3,700 | 0 | 3,700 | 無 |
| **合計** | **74,750** | **0** | **74,750** | **缺乏完整日級欄位** |

直接阻擋原因 `G2_SHARED_TEMPLATE_NOT_YET_APPROVED`。目前在新正式模板登錄簿 `R3_G2_APPROVED_SHARED_TEMPLATES_V1.json` 仍沒有任何核准模板、逐筆原生綁定登錄 `R3_G2_NATIVE_BINDINGS_<SOURCE>.json` 也尚無已核證資料。這不表示資料損毀，而是公用規格與原件的審核證據尚未完成。

### 143項既有共用候選模板

- 候選組合依 `source × Dataset × 歷史月份分期` 產生，並非143個實際獨立版式；通過獨立來源文件/日級生效時間核證後，正式模板可能需要拆分、合併或標示不適用。
- 上一次143項官方審核結果仍為0/143 approved；143缺資料集歷史版次核證、119缺完整必要欄位、72缺原生主鍵，原因重疊。
- 新 G2 認證邏輯使用 `scripts/v097_r3_g2_shared_contract_engine.py`：
  1. 共用模板必須有 Dataset 官方起始日、日級格式版本窗口、原生版式、必要/可選欄位/別名/主鍵、獨立核准紀錄。
  2. 用 Google Drive 中**真實官方文件 bytes SHA** 與**獨立審核紀錄 bytes SHA** 再核實，不靠 URL、布林旗標或字段猜測。
  3. 個別原件需獨立綁定 `source_id + source_sha256 + dataset + historical_era + native_layout_id + source_data_date`，其中日期亦須有獨立核證來源及 SHA。
  4. 當且僅當唯一正式模板符合、逐筆證據有效時，先產生候選憑證，寫入隔離 Drive 後**獨立讀回**才計入 G2 PASS。不存在證據時維持 HOLD。

### 真實70筆原生蒐證結果

|來源|抽樣|原生格式|可擷取表頭候選|JSON原生日期候選|從路徑提取候選年月|
|---|---:|---|---:|---:|---:|
|TWSE|10|ZIP 10|0|0|10|
|TPEx|10|ZIP 10|0|0|10|
|MOPS|10|ZIP 10|0|0|10|
|TDCC|10|HTML/XML 10|0|0|10|
|TAIFEX|10|CSV 8 + ZIP 2|8|0|10|
|NDC|10|JSON 10|10|10|10|
|FinMind|10|ZIP 10|0|0|10|
|合計|70|SHA均一致|18|10|70|

這些都是 **native source candidate**，不是官方核准格式、更不是正式交易/公告日期憑證。ZIP 必須解壓逐 member 核實完整原生表頭/來源，HTML/XML 要核原生內文的資料集和公布日期；否則不能自動核發 G2。

## Google Drive 與保護措施

- 全量來源收據：`JARVIS_C1_v097_LIFECYCLE/03_DATA_QUALITY/R3_G2_COMMON_TEMPLATE_RECONCILE_ISOLATED/r3_g2_full_source_<SOURCE>_run_44251486666.json`
- 全量 G2 QA Master：`r3_g2_shared_master_run_44251486666.json`，Drive ID **1Sx_We6L7o17xoUGQ6jyxiFdltt3JC9Oe**（寫入後獨立讀回成功）。
- 70筆原生證據：`03_DATA_QUALITY/R3_G2_NATIVE_FORMAT_EVIDENCE_CANDIDATES/r3_g2_native_candidates_<SOURCE>_run_44251892156.json`；另有對應 Master。
- **不更動 Bronze、不執行 Silver/Gold、不合併 PR、不動舊 R1/V3 Master。** 正式 R3 G2 完成率 0%，是準確的阻擋狀態，不是假100%。

## 資料日期規則修復（重大根因）

原凍結母體沒有可直接核證的日級資料日期。若只從 `source_path` 猜 YYYY-MM 就套用模板，會在期交所2017-05-15、財報公告修訂與 TDCC 週資料等情況產生嚴重的未來資訊偏差。

新逐筆原生證據的必要欄位：`source_data_date`、`source_data_date_verified=true`、`native_date_evidence_sha256`；無法從檔案內文與官方元資料核實的，只能作為候選並 HOLD。

## 後續需真正完成的正式核准

1. 利用七來源原生蒐證清冊+此前 SchemaV2/V2.1 解析履歷，建立各 Dataset 原生格式群組並補官方歷史文件。
2. 以實際官方證據核定真正存在的各模板起始/終止日期；區分官方資料集起始日、格式起效日與 Bronze 最早保存日。
3. **先核至少一種完整官方版式+原生檔案**，完成模板/原件綁定兩份證據與真實 G2 憑證寫入讀回；後續才按照已核准模板覆蓋相同格式的其他檔案。
4. 對尚無原生證據的 ZIP/HTML/PDF 建立有大小上限的原生 member 解析/格式身份提取，保留舊記錄增量處理。
5. 然後再用全量 worker 精確重用正式 PASS，沒有憑證的維持 HOLD，不能只重複對空核准登錄簿跑74,750次。

### 目前狀態

**G2 共用模板與74,750筆逐筆比對機制已真正連接並實測；但正式官方模板及原件核准所需證據尚未建立，故正式 PASS 仍為0。** 接下來的工作是「取得、核實與記錄官方各版式和真實原件的證據」，不是再次只跑同一個 HOLD。
