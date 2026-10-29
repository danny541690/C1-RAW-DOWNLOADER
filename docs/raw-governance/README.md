# 賈維斯RAW下載規則、測試與問題查詢入口

最新總彙整：20261029_R1。資料範圍及測試狀態以各版固定證據SHA為準，不能由workflow success推論資料完整。

- [測試結果總彙整](20261029/01_測試結果總彙整.md)
- [有效下載規則](20261029/02_有效下載規則.md)
- [問題追蹤表](20261029/03_問題追蹤表.md)
- [機讀登錄與158個證據索引](20261029/registry.json)
- [Google Drive同步位置及固定檔案ID](20261029/drive_sync.json)
- [Google Drive查詢資料夾](https://drive.google.com/drive/folders/1U5VHn3iPxnGbm2baUf27qYqt0Cq8wvBA)

後續測試紀錄要求（使用者2026-10-29指示）：每輪保存成功/失敗/取消/未執行、來源/期間/方向、case與run ID、SHA、錯誤原因、修正、重驗及下一斷點；沿用規則/問題ID，保留歷史。實際測試前先查本入口及原證據，不把舊報告已被後續解決的門檻當現況。

每輪結束先把報告提交GitHub，再用drive_sync.json的既有檔案ID更新Drive（保留版本，不重複建立同名檔）；兩端回讀確認後才宣稱同步完成。更新manifest雜湊並追加新版本，失敗記錄待同步。現在尚未安裝所有workflow的自動Drive同步hook，不能稱已全自動保存到Drive。現有Actions artifact有30/90天期限，長期證據以repo固定SHA報告及持久狀態分支為主；本次沒有複製全部二進位artifact/完整log到Drive。

ChatGPT只作查詢及交接入口，不能作唯一正式儲存。管理檔不是市場原件，RAW盤點工具應排除01_RAW/00_下載規則與問題清單，不將其算為資料涵蓋。
