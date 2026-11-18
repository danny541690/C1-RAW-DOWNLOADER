# JARVIS v0.97 R3｜首批真實 G2 公用模板認證及 320 筆增量完成（2026-11-18）

## 執行結論（正式 G2，非 G3/G4/G5 Silver Ready）

- **正式共用原生模板 1項**：`NDC_2026_CAPTURED_REVISED_XLSX_5SHEET_JSON_V1`；來源版本係**2026年10月23日已有封存證據**之國發會官方五張 Excel 工作表／衍生 JSON。
- **G2 逐筆 PASS 320 / 74,750**；**HOLD 74,430 / 74,750**，七來源計數精確吻合固定母體。
- 10筆首批個別證據發證：GitHub [44258064219](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44258064219)，正式獨立讀回。
- 309筆全量原生驗證：GitHub [44258835703](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44258835703)，10,389個原始欄位值及117個原始缺值一致；先保留1筆真正的比較例外。
- 最後2026-08缺值例外：GitHub [44259887707](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44259887707)，確認原 Excel 的8個文字 `…` 與 JSON `SOURCE_MISSING_VALUE` 和缺失清冊一致，缺值保持缺值、不自動填0，1筆正式證據讀回 PASS。
- **最快完整正式 G2 逐筆證據批次與74,750筆總表**：GitHub **[44260700121](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44260700121)**，320筆逐筆 certificate 的 SHA 在同一個**不可變、讀回驗證的 NDC 來源批次**中逐筆核對，最後7來源 Master 讀回成功。
- 舊式「每檔一個小 JSON」工作流另有 Run 44259288074、44260052709 的個別檔案鏡像工作，受同一 concurrency 控制；請勿將其尚未結束誤解為已經通過的「來源批次」G2 收據失效，也不得以未完成鏡像宣告全部完成 Silver Ready。

## 七來源 G2 統計

|來源|母體|正式 G2 PASS|HOLD|
|---|---:|---:|---:|
|TWSE|12,071|0|12,071|
|TPEx|13,200|0|13,200|
|MOPS|1,935|0|1,935|
|TDCC|40,384|0|40,384|
|TAIFEX|3,140|0|3,140|
|NDC|320|320|0|
|FinMind|3,700|0|3,700|
|**總計**|**74,750**|**320**|**74,430**|

**0.4281%** 為 G2 真正逐筆 PASS 率；不是 Silver Ready 完成率，也不是 Bronze 下載完成率。

## 官方原件及雙重檢證

- 官方真實原件國發會 XLSX：Drive ID `1bFKgv4V1uA08bvThkMl4xorLaNYbAdN0`，SHA256 `c035dc5bbd3fe91ca80a620fd84828a54e8c49885a1b3aa51db5e42857772c83`。
- 真實官方主機 `ws.ndc.gov.tw` 重新下載 bytes 與封存 SHA 一致：GitHub [44257356412](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44257356412)。
- 首10筆 Excel 5張原生工作表／JSON 源資料逐值比較：337值+3原生缺值、0不一致，GitHub [44257047358](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44257047358)。
- 增量跨全320筆依來源 file_id、SHA、日期、原生欄位、數值、缺值清冊逐筆驗證；真實差異分離，不改 Bronze。
- 本次核准為**2026來源修訂版快照的格式與原件證明**。其資料觀察月份可能早於來源快照數年甚至數十年；**不允許當作2001–2025年同時點已知的資料**。所有憑證明定 `source_publication_asof=2026-10-23`、`historical_backtest_eligible_before_source_publication=false`。
- 「獨立審核」目前是多個不同 Run 的**自動化官方網址 bytes 與原生檔案/欄位交叉驗證**，**不是人工核發或主管機關逐檔簽章**；任何更早日期的 PIT 證據均未認證。

## Drive 正式 G2 驗收存證（R3 隔離 QA）

- **320份逐筆正式 G2 憑證的不可變批次**：`R3_G2_BATCH_CERT_SOURCE_VINTAGE_ISOLATED/r3_g2_NDC_320_native_cert_shard_run_44260700121.json`，Drive ID **`1vkJKJvfZJFMJdkah-oXK4DoYXKv8eSro`**，完整批次 SHA `1d0ef637a60e3f01c3294390b7c1e74c77da000f6b2710fc80528616fe94eade`；每一筆含 source_id、Bronze SHA、憑證及憑證 SHA，讀回後逐筆驗證。
- **全量 G2 批次 QA Master**：`R3_G2_BATCH_CERT_SOURCE_VINTAGE_ISOLATED/r3_g2_74750_certified_batch_master_run_44260700121.json`，Drive ID **`1Bn1eAEHQ8az4v_sIxHezGPAO1U4gCmkS`**，寫入後實際讀回。
- **已核准格式登錄**：`R3_G2_APPROVED_SHARED_TEMPLATES_V1.json`，Drive ID `1EqH4T4FG2uxv2YiO8Jtj6Gy-w95_A2m8`。
- **320筆版原件關聯登錄**：`R3_G2_NATIVE_BINDINGS_NDC_V3.json`，Drive ID `1fRYdugN8jUM1weYX8fLeMbXwrrpy-_qR`，先前 V1/V2 憑證原狀保存。
- 原始證據及 review 對帳資料另存 `R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED`；所有報告均可由 GitHub Run ID 血緣追溯。

## 後續增量方向

1. 對剩餘143項歷史候選的其他資料集/原生格式，依來源先完成官方文件 SHA、原生版式、Dataset 起始日及 PIT 版本；不能複製本次 NDC 的核准旗標。
2. 從真實 ZIP member/TAIFEX 混合類型做下一種共用模板，官方期貨每日行情和價差概況/法人/大額交易人不能混當同一 Dataset。
3. G3 是全檔型別、單位與語意解析；G4 才是 Silver 輸入映射。**NDC 320 G2 PASS 不表示 G3/G4 PASS**，亦不得啟用 Silver/Gold 實體轉換。
4. 逐筆證據可以採來源不可變批次 + 每筆內容 SHA + Master 讀回，無須74,750個小檔造成 Drive 大量 RPC；舊單檔憑證與新批次可平行稽核但不可同時更新正式 G5 Master。

**安全**：原始 Bronze 唯讀；未合併 Draft PR #61；未切換舊 R1/V3 正式寫入；沒有執行 Silver/Gold 實際轉換。
