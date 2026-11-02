# 賈維斯 C1 統一問題總帳

最新整理版本：2026-11-02 R1。用途：搜尋下載問題、追蹤處理與重驗、保存跨對話證據。此次只新增管理紀錄，不變更RAW或線上排程。

- [Google Drive總帳資料夾](https://drive.google.com/drive/folders/1KqIZeoK10x_Hjoyh7NRffmTRODB-sT2c)
- [可搜尋／篩選的Excel總帳](https://docs.google.com/spreadsheets/d/1C5yWlF_UBZadAOPYAmD3PNAyh7nCkCQJ/edit)
- [28頁人員閱讀版PDF](https://drive.google.com/file/d/15jgggR-De-IILYZ9EZdZJgrRLeVlSuna/view)
- [問題索引JSON](20261102/issues.json)
- [歷次證據分頁索引](20261102/events_index.json)
- [來源清冊](20261102/sources.json)
- [範圍與版本清冊](20261102/manifest.json)
- [其他ChatGPT對話接續指令](CHATGPT_HANDOFF.md)

## 數字口徑與來源

本次收錄148份文件、89筆問題索引、1719筆證據事件。89筆含I/K/O不同命名與別名，不代表89種獨立根因，更不是89份資料缺失。事件包含文件段落、表格列、結構化測試及問題索引快照，不代表1719次HTTP錯誤。

來源為C1-RAW-DOWNLOADER的已追蹤docs／reports Markdown，以及C1-JARVIS五份十月初歷史參考；主要來源基線fe9737de6b5b166de50b1bafc4e6a4caa4fab358。前代內容只用於問題知識，不匯入前代市場資料／PASS。

**尚未完成整月所有Actions逐run日誌、來源分支全部狀態頁與所有歷史對話的逐筆對帳。** 未取得或未解析的證據不能填「沒有問題」。11/2數量是09:16來源報告快照，非即時進度。

舊registry.json只有24個I項，但Markdown列I01-I34。本次以完整人工表補入I25-I34，新增GOV-REGISTRY-LAG記錄差異。舊登錄與舊失敗不改寫。

## 如何查詢

Excel「問題索引」用來源／狀態／固定編號篩選，Ctrl+F查關鍵字；「歷次證據」保留全文、日期、行號對應連結及hash；「來源清冊」保留固定程式版本下的文件URL。長文字可點入儲存格查看全文。PDF用於手機閱讀問題與方案。

## 更新契約

1. 沿用固定issue_id；相似但尚未證明同根因的項目只記related_ids，不強行合併。
2. 每次發現、補抓、修正、重驗、重開追加事件，帶run／attempt、source／dataset／period／security、原件SHA、程式版本、結果及來源證據。未知欄位標UNKNOWN，不猜。
3. 程式修正、測試通過、資料修復和正式驗收分開。關閉必須附同一範圍的驗證；官方例外、暫停與排隊不能冒充下載成功。
4. 重建時保留舊事件；以固定事件ID與內容hash去重。舊版本目錄不刪，新版本另存，再更新本入口。
5. 若使用build_ledger.py重建，從repository根目錄執行；結果先檢查新增／變更／舊事件保留，再依events_index切分頁、生成閱讀檔並更新Drive／本入口。此腳本是可重現工具，不是已排程背景同步。
6. 這次建立的是人工啟動快照，沒有新增自動同步工作。既有來源日誌可持續寫原位，但不等於此Excel/PDF自動刷新。

## 跨對話限制

ChatGPT可經本入口／交接包讀取，不表示所有對話自動獲得內容或永久記憶已寫入。回答進度先查當前正式來源state與run；回答歷史問題先查本帳與原證據。保留失敗、取消、跳過與UNKNOWN，不把聊天文字當寫入成功回執。
