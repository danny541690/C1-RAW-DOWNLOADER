# JARVIS v0.97 R3 G2/G3/G4 真實證據修復結果 — 2026-11-18

## 實際執行與安全界線

- 執行分支：`r3-bronze-silver-ready-staging-20261118`，PR #61 仍為 Draft，尚未進入正式 R3 發布。
- GitHub Run [44243152359](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44243152359)：70 / 700 / 1000 實際凍結檔案，逐筆 Gate 稽核與 Google Drive 收據寫入讀回，成功。
- GitHub Run [44243499670](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44243499670)：同樣三組實檔稽核，新增 G2/G4 候選清冊持久化與讀回，成功。
- 兩個 Run 都未授權 Silver/Gold 轉換，也未修改 Bronze 原件、R1/V3 Master 或正式 G5。
- 「真實資料 Gate 進度」不等於「資料毀損比率」；沒有官方契約就保持 HOLD。

## 真實樣本報告

| 批次 | G2 PASS | G2 HOLD | G3 PASS | G3 HOLD | G4 PASS | G4 HOLD | Drive 讀回 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 70 | 0 | 70 | 0 | 70 | 0 | 70 | 通過 |
| 700 | 0 | 700 | 0 | 700 | 0 | 700 | 通過 |
| 1000 | 0 | 1000 | 0 | 1000 | 0 | 1000 | 通過 |

**所有實測主因：**`G2_MISSING_OFFICIAL_CERT`；`G3_UPSTREAM_G2`、`G4_UPSTREAM_G2_G3` 為依賴阻擋，並非已認定 G3/G4 本身解析失敗。三批次含重疊樣本，不可直接相加成1770個互異的檔案。

### 1000筆來源別

| Source | Sample | G2/G3/G4 PASS | HOLD原因 |
|---|---:|---:|---|
| TWSE | 143 | 0/0/0 | 缺已批准 G2 |
| TPEx | 143 | 0/0/0 | 同上 |
| MOPS | 143 | 0/0/0 | 同上 |
| TDCC | 143 | 0/0/0 | 同上 |
| TAIFEX | 143 | 0/0/0 | 同上 |
| NDC | 143 | 0/0/0 | 同上 |
| FinMind | 142 | 0/0/0 | 同上 |

### 已重用／盤點的來源證據

- 凍結母體 74,750 筆，七來源 baseline 清冊已確認精確筆數。
- 全來源 R1 G2/G3 正式 per-file registry 內容各為0（截至本次 Run，僅是這些登錄簿，並不否定其他候選來源證據）。
- 七來源舊 G4 mapping checkpoint 記錄數：TWSE 9,750；TPEx 9,750；MOPS 1,935；TDCC 9,750；TAIFEX 3,140；NDC 320；FinMind 3,700；合計 38,345。多數只有候選或缺證，**不代表有38,345筆正式 G4 認證**。
- 欄位候選 `HEADER_MATCHED_UNCERTIFIED` 為 TAIFEX 59、FinMind 24，合計83。
- 已建立 G2 歷史候選模板143項，另有以七來源資料集主鍵為基礎的 G4 輸入候選19種；它們不是已正式核准的模板。
- 官方文件參考入口以 `docs/V097_R3_G2_OFFICIAL_REFERENCE_CANDIDATES.json` 保存，**缺少逐資料集歷史版次與原生檔案確證，不可核發**。

## 實際 Drive 證據路徑（隔離）

`JARVIS_C1_v097_LIFECYCLE/03_DATA_QUALITY/R3_G234_FORMAL_REPAIR_ISOLATED/`

第二輪 Run 44243499670 已寫入並讀回下列檔案：
- `r3_g234_70_run_44243499670.json`，SHA256（JSON canonical）：`ec426469c870010159ca5e38e6d6d70711a59e3c0cd4a530cf7bb7c68f4ed99a`
- `r3_g234_700_run_44243499670.json`，SHA256：`a4f786c29b22ecabdc71939f619210bd479d543ec8b19f2c1290e6d0cb427710`
- `r3_g234_1000_run_44243499670.json`，SHA256：`c183b2e87b7e3ded0816168e1692effc44d991da916cb92b01d3e7b47cfdb245`
- `g2_historical_template_candidates_run_44243499670.json`
- `g2_official_reference_candidates_run_44243499670.json`
- `g4_seven_source_input_candidates_run_44243499670.json`

所有清冊均為 **CANDIDATE / HOLD**，沒有偽造資料集官方認證，正式 G2/G3/G4 仍為 0。

## 根本原因與具體下一步

1. 現有 `scripts/v097_g2g3_formal_contract_publisher.py` 是候選審查報告發布器，不是正式憑證發證器。其 `g2_verified=0`、`g3_verified=0` 等欄位原本就固定，不能期望自動變成 PASS。
2. 先依141+個候選群組按 `source/dataset/era/native_format` 聚合，逐群確認官方規格、原生欄位、SHA、有效日期、PIT 與獨立審核紀錄。不能僅靠來源首頁連結或模糊欄位相似度核准。
3. 將核准的共用模板以 immutable 版次與官方來源文件 hash 儲存在 Drive，再把每筆凍結 `source_id + SHA + dataset + era + native_format` 綁至模板後核發 G2 per-file cert。
4. G3 增量匯入既有全檔解析：比對 G2 必填欄位、原始單位、主鍵、交易日期與歷史有效證券身分；依賴證據不完整列 HOLD，不重跑已正式驗證且版次未變之解析。
5. G4 對每個已通過 G2/G3 的資料集套用七來源輸入模板，真實核對來源欄位、單位、PIT 與目標欄位；不得建立 Silver。
6. **本次70筆試驗沒有一筆通過 G2，所以正式的後續700/1000擴張驗收條件仍未達成。** 700/1000只是獨立的實檔 HOLD 原因盤點；不能代表正式擴大驗收已通過。正式74,750逐筆憑證認證應在先有可用官方核准模板後執行，避免浪費相同的無效重跑。

## 固定原則

Bronze 永不修改；來源沒證據不能變成 PASS。沒有任何實際 Silver/Gold 轉換或正式 G5；R1/V3 舊系統未切換，R3 PR #61 未合併。
