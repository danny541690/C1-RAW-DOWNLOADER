# JARVIS C1 v0.93 — Google Drive 正式下載保存／連線故障處理 SOP
更新：2026-10-18。適用：2024 四來源原始資料首輪與未來正式年度下載。

## 事故證據
GitHub Actions run 39139589993 於 2026-10-18 15:17 UTC 停止。Traceback 指向
`scripts/annual_actual_firstpass.py:113` 的 `put_json(... IN_PROGRESS ...)` →
`Drive.put()` → Google Drive API `files.create(...).execute()`，
由 HTTPS socket `TimeoutError: The read operation timed out` 引發。
這次不是來源資料 API 直接傳輸失敗，而是 **Drive checkpoint 建檔回應逾時**；
不能由 TimeoutError 推斷 Google Drive 實際沒有寫入。

## 官方依據
- Google Drive API 錯誤處理：https://developers.google.com/workspace/drive/api/guides/handle-errors
- Google Drive API 配額與截斷指數退避：https://developers.google.com/workspace/drive/api/guides/limits
- Google 官方 Python API 用戶端 HttpRequest.execute(num_retries)：
  https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.HttpRequest-class.html

## 程式規範
1. `files.list/get_media/create/update` 遇到短暫 socket timeout、連線失敗、429、5xx，採首次 + 最多 3 次重試，指數退避及少量隨機抖動。注意：某些 403 為可重試的 rateLimitExceeded 或 userRateLimitExceeded，不能只依 HTTP status 判定；401、授權遭撤銷、其他無權限 403、400 應停止並列為系統性阻礙。
2. 對 **create/update 回應逾時**，再次寫入前須 `files.list` 用父資料夾 + 名稱查已建立的檔案；若存在，回讀 SHA256：
   - 雜湊一致＝已保存，跳過重複建檔；
   - 不一致＝保留問題證據，若可安全修復則用檔案 ID update；
   - 重複名稱或列表未知＝不可盲目 create，列為待核對。
3. 正確性門檻：原始 bytes 上傳、回讀 SHA256 一致、記錄 bytes、來源、內容年月、抓取時間後，狀態才可為 SAVED_BASIC_VALID；數值與 PIT 未驗證時絕不能標為 QA_VERIFIED。
4. 每次來源請求前先持久化 `total_attempts`；不得因 GitHub Job 重新啟動而將同年度同單元的 4 次上限重置。Drive 操作重試另行計數，不可重抓已驗證來源原始檔。
5. 每完成一個單元就儲存原始資料和 checkpoint；每月保存 MONTHLY_PROGRESS.json/.md、MISSING_UNITS.csv、REPAIR_QUEUE.json。無法寫入核心 checkpoint 時，應停止依賴該 checkpoint 推進，不得假報完成；待權限或雲端服務恢復後再接續。
6. 一個來源單元失敗可以延後補抓，並繼續同月其他來源及後續月份；但 Google Drive 整體無法存檔屬全域持久性故障，必須記錄 BLOCKED，不能將暫存資料假報已保存。
7. GitHub workflow 排程、跨 job 自動接續、來源覆蓋及月報實際保存，必須個別經過真實端到端驗證，不能把測試樣本成功等同全市場正式完成。
8. 資料目錄：`C1_0.93/01_RAW/{year}/{source}/{YYYY-MM}`；checkpoint 和報告依已驗證的控制、報表目錄保存。資料保存在**私人** Google Drive；公開 GitHub 僅保留不洩漏敏感資料的程式與工作結果。
9. OAuth Testing 發出的 Refresh Token 可能失效；若遇 invalid_grant 或 invalid_client，停止盲目重試並回報憑證問題，不曝光 Secret。

## 目前修復狀態（依程式碼；非生產驗收）
- `annual_actual_firstpass.py` 已加入 Drive list/read、create/update 的受控重試與建立後回讀 SHA256 核對。
- 2024 partial workflow 已設定於該下載程式修改時自動啟動；run 39140006239 於本次記錄時仍在執行，尚無最終結果。
- **尚未宣稱** 正式全市場、完整 12 個月份、跨 Job 自動接續及持久化報告全部通過。
