# 四路檢查上線前測試續報（2026-10-24）

## 舊排程暫停

使用者已明確要求暫停舊一至四。main 一次性維護工作 40068486991 已成功停用 v093-official-only-two-ended.yml 與 v093-official-only-repair.yml，並確認兩者無執行中批次；14:01 台灣時間完成確認。RAW、進度與既有收據未刪除；五、五之一、六、六之一、七未變更。

## 新增測試與修正

- 財報重解析不再只是 next_action：接入嚴格矩陣 transform/validate_output，寫至獨立 REPARSE_STAGING，再讀回核對 SHA 與每個原生儲存格。保留 RAW，仍不自動關閉會計、單位或 PIT 旗標。
- 缺公司之來源回應與解析器錯誤分開；來源公司不完整時拒絕寫出成功結果。
- 每路持久化 RETRY_MONTHS.json，進入主掃描前處理到期待補，即使已 PAUSED_AT_MEETING 也不停止原有待補工作；冷卻中的項目不立即重抓。月份寫入仍取得既有 fenced month lease。
- 新增輸入 SHA 錯誤不寫出、損毀回讀拒收、過期 writer 不發布成功收據、原始檔與成功收據保護、完整 worker 重解析不發來源請求、重解析失敗也不重抓有效 RAW 等測試。

## 真實原始檔重播

Drive 原始 ZIP 1oOiOX6zDRAUoWWbfJtQNuyLJTO3rHSAk，6份財報檔中5份通過原始 SHA、嚴格轉換、隔離本機寫出再回讀與儲存格對照，共4975個數值儲存格。此結果是本機隔離測試，並非正式 Google Drive 輸出或全量財報驗收。

第6份（654fa677c284792a1eb211ea）請求20家公司，回應reportName只列16家，缺9103、9105、9110、9136，且scope header仍20欄。列 SOURCE_CONTENT_INCOMPLETE，不補造、不略過錯欄、不算重解析成功。詳見 four-lane-reparse-replay-20261024.json。

## 未達上線門檻

新四路正式排程仍未啟用。仍須正式隔離 Drive／GitHub 整合驗收、缺公司或失效端點的實際來源補抓、完整月份母體與語意/PIT驗證。既有全測試基準內兩項期交所日期測試不符仍未以刪除測試掩蓋；本輪只報告相關測試結果。新派生輸出不能直接當成正式資料庫已修好。
