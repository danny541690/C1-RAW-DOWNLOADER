# JARVIS v0.97 R3 G2｜七來源歷史格式公用模板庫正式建立與資料庫對帳（2026-11-18）

## 實際執行結果

GitHub Actions：[Run **44263828295**](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44263828295) **SUCCESS**，七份 source-owned versioned template library、七份逐筆 frozen source cohort compare、1份 QA Master 均寫入 Google Drive 並回讀相等。

**架構：僅7份來源主模板。** 每份主模板底下保存 Dataset → 歷史分期 edition window → 該時期原生格式候選 → 必要/可選欄位、欄位別名、主鍵、單位 → 官方證據/核准狀態。2000–2026切三期只是示例；目前歷史登錄中各來源實際分期：TWSE 4、TPEx 5、MOPS 4、TDCC 2、TAIFEX 2、NDC 6、FinMind 1。這些歷史期別目前多為來源級候選，**不是所有 Dataset 都有對應正式核准的官方格式**。143是上述七個主模板下 *Dataset × 來源期別* 的候選組合總數，不能誤稱143個正式獨立格式。

### 七份來源主模板與實際清冊匹配

|來源|Dataset種類|現有來源級歷史候選期別|候選Dataset×期別組合|凍結資料數|路徑年月候選數|重用已核准G2|HOLD|
|---|---:|---:|---:|---:|---:|---:|---:|
|TWSE|8|4|32|12,071|12,071|0|12,071|
|TPEx|7|5|35|13,200|13,200|0|13,200|
|MOPS|6|4|24|1,935|1,935|0|1,935|
|TDCC|3|2|6|40,384|40,384|0|40,384|
|TAIFEX|6|2|12|3,140|3,140|0|3,140|
|NDC|5|6|30|320|320|320|0|
|FinMind|4|1|4|3,700|3,700|0|3,700|
|**總計**|||**143**|**74,750**|**74,750**|**320**|**74,430**|

**對帳正確性：** 七份 frozen source manifest 總筆數完全符合74,750；七來源每份實體 file_id / sha256 / source_path 的清冊均納入逐筆映射。所有 source_path 有 YYYY-MM 字樣可作歷史模板候選定位，但該日期**並非已核實的內容日期或發布日期**。此 workflow 沒有重新下載或解析全量原始檔 bytes，因此不得把其「格式匹配成功」描述成74,750筆正式內容通過。

**正式核准**：只重用先前 NDC 的 320 筆不可變 G2 source-vintage 憑證，且代表2026-10-23來源快照，禁止當作該日期之前同時點公開的歷史資料。其他六來源先前 SHA 60/60 的實體原生 sample 已納入各來源的比對血緣，但正式G2保持HOLD。

### 現行七來源主模板在 Drive 的獨立檔案 ID

|來源|七主模板之一|全量逐筆比對 QA 收據|
|---|---|---|
|TWSE|`1CcSbie9QpzzeRB-eLZxgaiRDrHBq3STN`|`1f0D7nJAMGhXxqfjiGH9edFs-ro2f23n0`|
|TPEx|`1QI8SKedLIf5z-iwwGsw9ffx0c0oztNb4`|`1p43RVkLK1Cf7Lt_GjNXnWt9mZYp7j1Qc`|
|MOPS|`1zsI7qO39d-qkLWkMK72Ea1FnOPvhOPLb`|`1YMJ-rnhiFMN1fWj8LAOkefvPOx73BWQl`|
|TDCC|`1cmYXH5RUfSs782rRshCncNLytqcIv_1t`|`1vVkFpVIGKDJZJFiGMvy980Lu6Gr0ISM3`|
|TAIFEX|`1wQRJF3f56gJJ0K0WTQ0OtPOZvIQvqI7I`|`1eOKb_MYwimCJ1Oocq-LcvkeDZzDAuneJ`|
|NDC|`1nEyC6jEfJYmKV5smXoBbwupArNa6sSMo`|`1zoQWUwer3hUImJ8MsPFBspROxsagzPS1`|
|FinMind|`1GuTBe19NNAfie4Lssq6f3WfOmmNZ0kOe`|`1zl0D0qXmkbnUd5v3Kt-NId5W6Hlktsy8`|

Drive 資料夾：`03_DATA_QUALITY/R3_G2_SEVEN_SOURCE_PERIODIC_TEMPLATE_COMPARE_ISOLATED/`。

**全量新版 QA Master**：`r3_g2_seven_source_periodic_templates_master_run_44263828295.json`，Drive ID `1bL0BpkCS8HPvPtU0rg7PYcyA7qP5RfjK`，remote readback PASS。

### 下一段不得跳過的正式資料集格式核准

1. 由來源歷史候選期別縮小 Dataset 的實際生效版本，不同 Dataset 不一定同時更版（例如 TWSE 一個來源可有四個歷史期別，但某個 Dataset 只存在其中一段或有額外日級改版）。
2. 查官方發布規格與原始下載回應；版本生效日若位於月中（例如 TAIFEX 2017-05-15），拆成精確的日級版次，不能把整月全部套一種格式。
3. 每個來源 Dataset 原生格式別名、欄位、主鍵、單位和改版日期取得可靠證據後，以來源 SHA 和實體成員內容連到模板；必要時區分原始封存檔與由此衍生的 JSON/ZIP。
4. 才由正式 G2 引擎核發 per-file certificates，寫入新 QA 批次、讀回 SHA，逐筆 PASS；其餘仍 HOLD。
5. NDC 320 證據原封不動重用；不要額外宣告G3/G4 PASS或Silver Ready。

安全：不更動原始 Bronze 0.93/0.97，不合併舊 Master，不執行 Silver/Gold。
