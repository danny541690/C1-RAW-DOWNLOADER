賈維斯 v0.93：修復接點與身分對帳測試
日期：2026-10-22（Asia/Taipei）
狀態：OWNER_REPLAY_BOUNDARY_AND_IDENTITY_TESTED_NOT_DEPLOYED

本輪結果
GitHub Actions 全套 325 項通過，比前次增加 19 項；帳本／接點測試累計 44 項。獨立雲端 CAS 測試與三筆真實舊收據的身分對帳測試均通過。
測試紀錄：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39713259385
程式提交：dac761a1e0f348080b63b517c8788de32c559740。

新增程式
scripts/v093_stage06_owner_replay.py 提供 QA1、PRICE、FINANCIAL、CHIP 的修復接點。領取限定處理器版本、規則版本與支援的缺失種類，避免錯誤版本搶走任務。讀取原始資料先檢查輸入雜湊，輸出及驗證證據存檔後均須讀回核對；通過該類缺失的檢查並仍持有執行權，才提交結案回執。
測試包含四個非 RAW owner、錯誤輸入／輸出／驗證證據、處理過程鎖過期、原始工作者失去執行權、中斷後重用不可覆寫輸出、禁止不同內容覆寫、版本與規則篩選、數值缺口不能當解析缺口結案，以及 RAW 必須走獨立持久請求接點。

三筆舊紀錄的身分對帳
以原本隔離回執雜湊與原始 RAW 索引的 unit_id、RAW SHA256 精確比對，三筆均找到唯一對應。
170f0f0bb6fa2cb603e0f36c：TWSE／capital_reduction／2026-10。
8b77e18f8f611c974c9f0026：TPEx／indices／2026-10-20。
cbaebbfcedd830a234aeadb1：TPEx／indices／2026-10-19。
原始回執被修改、RAW 雜湊不同、原始身分有多個對應時都拒絕解除待對帳。重複對帳不會重開或重建同一缺口。

目前測試帳本
16 個缺口、16 個修復任務；身分待對帳 0 筆，已對帳 3 筆。
16 個任務全部維持 BLOCKED_APPROVAL，候選處理器 CANDIDATE_MAPPING_FIX_V1 尚無真實修正與驗收證據。
真實資料修復完成 0；本輪市場來源下載 0。身分對帳完成只代表知道來源、資料集與期間，並不代表數值或 PIT 已驗證。
最新完整 JSON 另存私有 GitHub state/stage06-validation/PRICE_202610_TEST_NOT_LIVE.json；既有 Drive 的 13 任務 JSON 為前輪歷史測試快照，本文件為最新接續點。

正式整合仍未完成
接點目前由測試後端驗證，尚未接入現有五條 live worker。正式 Drive 發布後端仍須落實執行權檢查與不可覆寫寫入；RAW 補抓接點、驗收過的解析修正版本、完整預期單元登錄與資料集適用範圍也尚待端到端驗收。
這次沒有啟用第六條常態自動修復，沒有修改五條排程的下載規則、60 分鐘預算或游標。numeric_verified=false、pit_verified=false、production_data_approved=false，新來源啟用清單為空。

下一個中斷點
先針對 16 個任務中的 TPEx 指數與 TWSE 減資／除權息等資料，補上符合資料集身分與日期語意的解析修正及真實輸出驗證；不要把指數缺少個股代碼直接視為下載缺漏。之後接入各 owner 的正式讀寫後端及 RAW 請求／存檔回執，再進行端到端修復驗收。只有通過後才啟用常態第六條排程。

最新 Google Docs 驗收與接續點：https://docs.google.com/document/d/1tYYc808waYE-qFFbxhFz6gT7hNxCSA79IPCJkpCKF9A/edit?usp=drivesdk
