# 賈維斯 v0.93：Drive 發布、修復回執與排程鎖合併驗收

日期：2026-10-22（Asia/Taipei）。本報告只涵蓋第六階段的上線前接點驗收；正式第六條排程仍停用。

## 本輪修正

新增 FencedGitHubStore：在固定 GitHub head 讀取排程 owner／fence／期限與缺失帳本；建立以該 head 為唯一父提交的新帳本，再以非強制 fast-forward 發布。任何中途插入的提交都會拒絕舊 head 的發布；若只是其他合法寫入，重讀後重試；若 owner 或 fence 已改變，舊程序被拒絕。正式鎖路徑另核對 stage 對應的 pool，不允許 PRICE 借用 RAW 鎖。

發布前重新檢查期限，距 owner 鎖到期至少保留 60 秒；HTTP 呼叫逾時 35 秒。修復任務的領取期限不超過外層 owner 鎖期限減 60 秒。這是有期限檢查的 GitHub 分支版本發布，不是 Drive 與 GitHub 的跨系統原子交易；Drive 產物先保存為候選，只有成功的 CAS 回執才取得權威狀態。

新增 DriveImmutableArtifacts：僅允許明確標示 ISOLATED_TEST_ONLY 的測試資料夾，以邏輯鍵及內容雜湊命名，從不更新既有檔案。上傳後讀回核對，回應遺失先對帳；同內容重複檔可依雜湊對帳，不同內容或損毀檔拒絕發布。完整 Drive 檔案參照只保存在私有驗證檔；公開測試帳本只有不含檔案 ID 的參照與雜湊。

第一輪真實雲端測試發現初始化錯誤：其他 GitHub 寫入造成的暫時 409 被誤判為帳本已存在。已修正為讀回確認後重試相同快照；內容不同則拒絕覆寫。新增測試確認分支衝突、建立回應遺失及不同既有快照的處理。

## 驗收範圍

- 本機與雲端完整回歸各 370 項通過，較上輪新增 22 項，第六階段累計 89 項。
- 真實雲端測試使用獨立 Drive 資料夾及獨立測試鎖、帳本，沒有取得或改寫現行五條排程的 live 鎖，也沒有修改其游標、預算或下載規則。
- 使用前輪已驗證的四份真實原始資料樣本：TWSE 減資、TPEx 除權息及兩個交易日的 TPEx 指數。完成真實 Drive 寫入、讀回、原生數值比對與 GitHub 帳本結案。
- 另在回執發布邊界故意釋放並更換測試 owner／fence，驗證舊程序不能發布；新程序於原任務領取過期後重用原產物，提交新的驗證回執。
- 真實 Drive 測試另建立同內容重複候選檔，驗證對帳後重用；不同內容覆寫會被拒絕。

## 仍未核定的部分

測試後端仍限制為隔離資料夾，production_data_approved=false、owner_runtime_integrated=false。現行五條 worker 尚未接入修復消費流程，第六條 enabled=false；正式候選 16 筆任務未因本輪測試改為已修復。

接續工作是正式 owner 修復接點與輸出契約相容性、RAW 補抓接點及完整預期單元登錄。數值單位語意、PIT 與全市場完整性驗證仍維持獨立未通過狀態。不得以這次的安全發布驗收代替資料完整性核定。

## 最終實測證據

- 結果：DRIVE_FENCED_PUBLISH_INTEGRATION_PASS_NOT_DEPLOYED。
- 真實 Drive 完整重放 4 份樣本，逐格核對 737 個數值；另有 1 筆更換 owner 後的恢復重放。
- 舊 owner 於回執發布邊界被更換後，舊提交未發布；接續 owner 重用既有輸出，task fence 由 1 遞增至 2 後成功結案。
- 同內容重複物件對帳成功，異內容覆寫被拒絕；Drive RESULT 與 GitHub CAS 結果讀回一致。
- 隔離測試鎖最後已釋放（last_fence=2、lease=null），現有 live 鎖與游標沒有寫入。
- 最終成功 run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39717112663
- 初次初始化失敗 run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39716874280
- 修正提交：c8b3eb784ea542a05c04e3f136544175b4f872d7；原始整合提交：ac7fb4f8f6c43e5069c6e5bde924641ea3fb7854。
- 真實測試後端目前仍限制 ISOLATED_TEST_ONLY；不代表已啟用正式資料發布。
