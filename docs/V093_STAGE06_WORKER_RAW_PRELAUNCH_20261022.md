# 排程六：worker 接點與 RAW 修復上線前驗收（2026-10-22）

狀態：TESTED_NOT_DEPLOYED。第六條 enabled=false；五條既有工作的 60 分鐘預算、下載規則與歷史游標沒有修改。

本輪新增 26 項測試；本機完整回歸 396 項通過，第六階段累計 115 項。程式提交 b30f3a1d541ef9ff618e850b40cbfc9fbd2529bd；接手測試依實際租期修正提交 8e9a3a53d7411d0ad7cac55b36b0118531b76f92。

## 已實作與測試

- 現行 Worker.run 已加入預設關閉的修復入口。只有明確注入 test_only runtime 才可領取測試任務；未設定時不讀遠端帳本。正式模式仍明確拒絕啟動。
- QA1／PRICE／FINANCIAL／CHIP 的 owner 路由、同一 owner/fence 綁定、處理期限及游標保護。時間不足時釋放尚可安全延後的任務，未知 HTTP 意圖不釋放。
- 實際 Worker.run 的本機隔離呼叫測試通過；一般 consume 仍會執行。既有 QUARANTINED output_key 不會被原流程重算，新修復輸出另存 stage06 版本路徑，保留原隔離證據。
- RAW 修復合約：官方優先、FinMind 僅限有相容證據的個股缺口；請求前保存意圖與原 RAW 持久 hold／次數；最多四次不重設；逾時未知先對帳；已存第四次回應可重用，不送第五次。
- RAW 保存意圖或傳輸發生 OSError，向外拋出並停止當輪 worker，不能繼續一般下載。這是保守停止，不代表原 RAW 持久接點已安裝。
- INDEX／SECURITY 與價格／報酬指數的修正版 Parquet 可被隔離消費端讀取。指數不杜撰個股代碼；輸出仍 STAGING_ONLY。
- 缺少單位、數值語意、PIT、母體、完整範圍或已核准處理版本任一證據即阻擋分析核定。預期單元缺少來源範圍、交易日、母體或可得性證據時 HOLD；不適用單元另列。

## 測試邊界

RAW transport、native.current／record_intent／finish 與預期單元目錄採可注入的測試合約；尚未連接正式來源 HTTP 或正式 RAW 帳本。其他 owner 的路由測試使用測試 validator；不代表 FINANCIAL／CHIP 全類別真實資料已完成端到端核定。消費端相容性是新 reader 契約與既有 worker 的入口測試，不代表所有下游分析消費者已遷移。

沒有新增市場來源下載，沒有改寫正式鎖／游標，沒有開啟常態排程六。16 筆正式候選仍 BLOCKED_APPROVAL，既有隔離解析試驗的 DONE 不等於正式修復。

## 上線前仍須完成

1. 將 RAW provider transport、原 RAW 持久計次／hold／保存回執與修復帳本接成同一 owner 的可恢復流程；用受控真實缺口驗證逾時、失鎖、重啟與不重抓已存資料。
2. 將 QA1、PRICE、FINANCIAL、CHIP 的正式帳本、核准 processor、來源讀取與證據 validator 綁定 runtime；新輸出需由正式消費端辨識與核定。
3. 建立有證據的預期單元登錄與增量對帳；未知範圍保持 HOLD。上線不必等待 2000–2026 全部歷史驗完，但不能把未知覆蓋率當完成。
4. 在正式綁定完成後做有界上線試跑、讀回回執與回復演練，再評估啟用第六條常態排程。

numeric_semantics_verified=false、pit_verified=false、production_data_approved=false、owner_runtime_integrated=false。

## 雲端合併結果

GitHub Actions [39724099017](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39724099017) 成功：396 項完整回歸、真實 Drive／GitHub worker bridge 測試均通過。4 份原始樣本、737 格獨立核對、不可覆寫保存與讀回；舊 owner 發布被拒、新 owner 在 task fence=2 接手結案且重用既有輸出；相同內容重複檔對帳與異內容拒絕覆寫通過。最後測試 lease=null、last_fence=2。

雲端 bridge 使用隔離的 worker 形狀 context，並由真實 fenced store 驗證 owner；實際 Worker.run 呼叫修復入口則由本機隔離測試驗證。不能將兩者合稱正式五條 owner 全面接入。

另 [39723908488](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39723908488) 的完整回歸與隔離帳本 CAS canary 成功。第一次 bridge 試驗 39723908527 因測試仍假設舊的固定 claim TTL，接手尚未到期而失敗；已改為讀取實際 expires_at，第二輪完整通過。
