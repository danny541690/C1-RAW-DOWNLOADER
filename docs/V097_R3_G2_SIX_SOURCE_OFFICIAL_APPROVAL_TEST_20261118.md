# JARVIS v0.97 R3｜六來源 G2 官方證據核證與第一批 TWSE、TPEx PASS（2026-11-18）

## 核證執行結果

**本輪確實執行，不是僅提出方案。** 在 R3 staging branch 調用 Google Drive 真實凍結 Bronze、前次60實檔原生 ZIP/JSON/HTML evidence、實際官方網站及原下載 API。

- [44266370461](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44266370461) SUCCESS：六來源各10個 frozen 原始檔，對照官方/供應商參考網址。14個官方/供應商頁面 bytes 已重取及SHA，60份逐筆 HOLD 原因寫入隔離 Drive 並讀回。
- [44266749919](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44266749919) SUCCESS：60份實檔 ZIP member 元資料檢查，來源官方下載 URL metadata 候選及文件類別分類，Drive 讀回。TWSE 10/10、TPEx 10/10、MOPS 10/10存在某種相關來源 URL 候選，但**不能假定 URL 與所有 ZIP member 一一對應**；TDCC 0/10、TAIFEX 0/10、FinMind 2/10（僅 provider API 入口）。
- [44267275612](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44267275612) SUCCESS：依 ZIP 內原網址重新下載8個實際官方歷史 API response，TWSE 1/4 及 TPEx 4/4 與某個原始 member 的 SHA 完全一致；其餘三筆 TWSE 現行回應與封存不一致，不能判為 Bronze 壞。
- [44267841704](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44267841704) SUCCESS：**TPEx 首筆來源版本 G2 憑證通過**。對2024-06-20估值 JSON 原始檔驗證官方端點實際 response SHA、ZIP完整 member inventory、manifest、2024-06-20原生日期及過去獨立 Run 44267275612；官方 raw bytes、Review、模板與 per-file certificate 全部 Drive 讀回。核准範圍僅「2026-11-18 可驗證的來源快照」，不是2024年的同時點歷史公布版。
- [44268565232](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44268565232) SUCCESS：**TWSE 首筆來源版本 G2 憑證通過**。2001-03-02 融資融券 MI_MARGN API 原始回應 SHA，ZIP member、原生日期、獨立歷史 API byte review，官方 raw bytes/Review/模板/cert 全部Drive讀回。2001年歷史回測 PIT 仍不可以因此通過。
- [44269047906](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44269047906) SUCCESS：**新增兩張 source-vintage cert 加入原 NDC320 的 R3隔離七來源 QA overlay**，每筆 source_id/sha256 比對74,750 frozen manifests，去重並檢查 source_publication_asof，不修改前一版 G2 Master、正式 G5、R1/V3。

## 七來源目前核證狀態（來源版本 QA Overlay）

|來源|固定母體|G2 QA 有效來源版本憑證|HOLD／尚無完整證據|已正式核准的本輪來源版本模板|
|---|---:|---:|---:|---:|
|TWSE|12,071|1|12,070|1（2001-03-02 融資融券的2026重新驗證版本）|
|TPEx|13,200|1|13,199|1（2024-06-20 估值的2026重新驗證版本）|
|MOPS|1,935|0|1,935|0|
|TDCC|40,384|0|40,384|0|
|TAIFEX|3,140|0|3,140|0|
|NDC|320|320|0|先前1份2026修訂快照模板|
|FinMind|3,700|0|3,700|0|
|**總計**|**74,750**|**322**|**74,428**|**現有3份有範圍限制的來源快照模板**|

**進度定義**：322是 **R3隔離QA overlay** 重用NDC320 + 新增TWSE1 + TPEx1，已驗證的來源版本憑證；以前的正式全量 G2 Master 尚未更新，其數字仍以已發布的舊版驗收帳為準。322不能視為 G3、G4、G5 或 Silver Ready PASS，也不代表2000–2026歷史資料時點可用（PIT）。

## 不得忽略：官方現行API原文一致 != 歷史當時版本未修訂

- **TWSE歷史觀察日期2001-03-02**，API網址 `https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20010302&response=json&selectType=ALL`，已核實的 source member SHA `7b9ae7e52b2978980d631a6920dea8a7ec9a1b8717fa37f5621a80ca6ba9c226`。
- **TPEx歷史觀察日期2024-06-20**，API網址 `https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?date=2024%2F06%2F20&response=json&cate=`，已核實的 source member SHA `f65df9512295854be52df5d8f3eeb4937b44894b41891019bd38a1c7ae4d2b30`。
- 兩張新憑證的 **source_publication_asof=2026-11-18** 是保守的「最早已驗證來源版本」時點，不是觀察資料的歷史公布日，不得用於2026-11-18以前的歷史策略回測。
- TWSE 其他歷史 API 3/4 現行回應與封存 member SHA不同：可能來源不同、網站回應修訂、API路由與檔案映射不一致；列 HOLD 查明，不可任意覆寫 Bronze。
- 來源級歷史分期候選仍在七份公用模板內；必須將 Dataset 原生格式及歷史版次獨立核證，不能將此3份來源版本模板泛化為整體143個候選時期 PASS。
- 官方文件來源範例：TWSE `https://www.twse.com.tw/zh/trading/historical/mi-index.html`，TPEx `https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html`，TAIFEX `https://www.taifex.com.tw/cht/3/futDailyMarketView`，TDCC `https://s.tdcc.com.tw/portal/zh/smWeb/qryStock`，FinMind `https://finmind.github.io/`。URL本身無法核准封存來源版次。

## 真實Drive證據及路徑

- 六來源官方文件與60實檔對照 Master：`03_DATA_QUALITY/R3_G2_SIX_SOURCE_OFFICIAL_DATASET_APPROVAL_ISOLATED/r3_g2_six_source_official_master_run_44266370461.json`，Drive ID `1kBGugpXpKllCBN-zg-AH26zIOB6uWA7j`。
- 六來源原始下載 URL metadata Master：`03_DATA_QUALITY/R3_G2_SIX_SOURCE_ORIGINAL_URL_PROVENANCE_ISOLATED/r3_g2_original_download_provenance_master_run_44266749919.json`，Drive ID `1yxgKk0vc92z0v70dEQ_AsDvi0Y88iMo8`。
- 官方8次原始 API 回應 SHA 比對 Master：`03_DATA_QUALITY/R3_G2_ORIGINAL_OFFICIAL_API_BYTE_CROSSCHECK_ISOLATED/r3_g2_real_official_http_sha_master_run_44267275612.json`，Drive ID `1bdaVkJ53V6Gt4VPVdzrvUeBZxPLbqY0l`。
- 新增 TWSE source-vintage 格式及綁定核准：`03_DATA_QUALITY/R3_G2_TWSE_FIRST_SOURCE_VINTAGE_FORMAL_ISOLATED`，核准證據 Drive ID `1_wqBVnDygf9gLZidhRW5gm_sB6CqhpYz`，G2 cert ID `1JVtCXIH642ZEwbNO-mLkDX1NNfaNOQV5`。
- 新增 TPEx source-vintage 格式及綁定核准：`03_DATA_QUALITY/R3_G2_TPEX_FIRST_SOURCE_VINTAGE_FORMAL_ISOLATED`，核准證據 Drive ID `1848WTvjSE6iF7HUG3KDBw-xP1-BIm0US`，G2 cert ID `1mVgK1dQ-VdGbo2ks1CEM7pj7g7loaZjR`。
- **七來源目前 G2 322 QA 對帳 Master**：`03_DATA_QUALITY/R3_G2_SEVEN_SOURCE_OFFICIAL_QA_COMPOSITE_ISOLATED/r3_g2_official_322_seven_source_QA_overlay_run_44269047906.json`，Drive ID `10zKBUEz2SDrLeRfxtGfC2IL7PDN5Im7O`，整份讀回確認。

## 其他四來源未完成的具體阻擋與下一個目標

- **MOPS**：原 ZIP 有 `mopsfin.twse.com.tw/compare/report` 的來源 URL；但 GET/POST/參數、財報種類、IFRS/TAXONOMY、原始報表發布日期及更正紀錄尚未與單檔 SHA 一對一綁定；需要先選一筆可重取原報表。
- **TDCC**：10份HTML/XML原始檔仍缺明確可重取來源URL、歷史16/17級及當時證券身分類別/週末有效日期的可查核證據。
- **TAIFEX**：10份含價差委託成交/選擇權/大額交易人，缺直接下載 URL、個別原生欄位/交易時段與歷史版次；1個 large ZIP 被資源上限保護，不是判為毀損。
- **FinMind**：10份JSON/ZIP封存，2份有 provider API入口；缺完整 `dataset`、request params、token可用性、來源時間與版本、可重取回應 bytes/修訂證據；FinMind屬補缺供應商，不能當成主管機關。
- 對每來源優先一個可完整原件對照、正式核准來源版本與單筆G2 receipt 的 Dataset，**不重複下載正確的整批Bronze**。任何資料缺證則保留 HOLD、後續再循相同方式增量擴展。

## 系統防線

原始 Bronze 唯讀；R3 staging分支 Draft PR #61 未合併；不改舊R1/V3 Master、沒有執行Silver或Gold，沒有動用正式G5發布器；測試結果與任何生產正式帳不得混淆。
