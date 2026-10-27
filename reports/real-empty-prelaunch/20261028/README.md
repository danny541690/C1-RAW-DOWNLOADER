# JARVIS 上線前實件合併測試：FinMind空資料回覆

日期：2026-10-28（臺灣）。完整本機測試805/805通過，新增4項。本機與GitHub雲端皆805/805通過，0失敗、錯誤、略過。PR #28已合併正式主線，commit c38acfb52670d5dbcae8dcd733954c46711fdb65。

已讀取2003-03的實際MONTH_STATE及拒收原件。原件40 bytes，SHA256 bd3deae97b9bbf5496db1c19da707df924ec244a8568f606429c0a6532ddca72，JSON內容status=200、msg=success、data=[]，與未解決收據的response_sha256一致。這是來源回傳空資料；不證明該公司當季無財報，也不是存檔成功。

快照共67個FinMind任務：59項保存狀態、7項FINMIND_GAP_UNRESOLVED、1項FINMIND_REQUEST_INTENT。7項空回覆公司代碼：1107、1207、1212、1221、1224、1306、1311；均IncomeStatement，2003-03-31。1437仍屬請求意圖，不能當作失敗或成功。最新狀態可能持續變動；明細以failure_trace.json的來源、快照雜湊及時間為準。

先前排程回報的5次失敗是當批作業次數，不能直接當成現在只有5個唯一缺口；未取得舊版收據快照前不逐項聲稱對應那5次事件。

新增實件測試：正確成功封裝的空陣列仍拒收；完整補缺失敗流程保留原件與雜湊、不發布合格RAW、不計成功、不關閉官方缺口；已嘗試3次不發送第4次；冷卻期間不立即重抓。實件回放使用mock傳輸，沒有額外請求FinMind市場資料。

現行隔離與重試邏輯通過驗證，本次只新增實件與測試，無需為空回覆修改成成功。待補處理：檢查各公司2003年申報適用性、官方舊制入口或其他歷史來源；保存的59項也不等於數值/PIT已全面驗收。全庫完整性仍UNKNOWN。

雲端驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40547705321
PR：https://github.com/danny541690/C1-RAW-DOWNLOADER/pull/28
