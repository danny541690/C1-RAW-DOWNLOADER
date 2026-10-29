# 十二入口共用worker接線與合併驗證（20261029 R9）

工作40857674847：12／12工作SUCCESS。對12種來源／方向組合呼叫同一reusable workflow與新共用worker；每路2筆明確標示的模擬任務，共24筆：預期基本檢查成功12筆、預期內容錯誤隔離12筆。不是24筆市場原始資料驗收。源站HTTP0、正式RAW寫入0，正式模式仍硬性拒絕。

12個具名候選入口已從設計列印改為呼叫jarvis-seven-worker.yml，來源／方向逐一與既有config比對；檔名保留原-preview.yml以維持既有連結，但預設模式改為entry-validation，權限僅供QA Git狀態與紀錄保存。入口仍只有workflow_dispatch，沒有cron。production選項會在任何Git／來源／正式RAW操作前拒絕，不能誤解成已能正式下載。

真實執行範圍是一次matrix的12組呼叫共享入口；12個具名wrapper完成靜態來源／方向/預設模式/共用入口綁定核對，未逐一對12個具名檔案送workflow_dispatch。候選版本64f8a8262c69cb5cd0e755f833c78d6503ccc449。

新run_batch共用worker已實作：

- 每筆領取後綁定該任務的adapter，不能整批共用一個錯誤案例。
- 優先對帳已存檔的中斷任務，再處理READY；恢復不增加來源下載次數。
- 內容錯誤或adapter缺契約逐筆隔離，繼續後續任務；同批不重複領取失敗的對帳任務。
- 有單位數與時間上限，保存每方向last_batch、狀態數與尚可處理量；沒有工作時不睡一小時，後續可依ready_remaining接續。
- 不重置舊attempts；source hold／cooldown仍由共同Coordinator控制。

候選12組各自經自動publisher保存至Git與Drive並讀回SHA，12／12份發布收據成功。收據含各自file_id與固定record_sha256，詳見remote-results.json；不是此次手工拷貝假裝自動。

全部完成後另由獨立連線重新讀取七來源遠端state.json與頁面：TWSE/TPEx/MOPS/TDCC/TAIFEX各4筆，NDC/FinMind各2筆；合計24，來源／方向綁定正確、attempts全為1、雙向last_batch各自保留，沒有互相覆蓋。本機138項回歸、12份受控入口設定核對全部通過，含正式模式先於任何Git/來源操作被拒絕，以及中斷存檔恢復失敗不阻擋下一筆。

Git QA狀態：jarvis-source-preflight/entry-40857674847-1/{source}。自動Drive紀錄位於RAW管理目錄下各RUN_40857674847-1-entry-{source}-{direction}。本批只碰隔離控制與驗收紀錄，沒有啟動原始資料庫正式修補。

尚未完成的實作（不能靠重跑同樣測試解決）：

1. 把已驗證的七來源原生讀取/下載/校正adapter接到run_batch的逐任務factory，並接正式舊紀錄匯入與適用性放行；目前CLI只有入口QA，production明確阻擋。
2. 各來源有證據缺件的正式下載→不可覆寫保存→讀回→補正→重驗實測；TDCC先前一筆已有隔離QA下載證據，其餘來源不能混算。
3. 來源共同配額、心跳與負載的正式實測，通過後才解除正式門檻與開啟自動觸發；三天全庫完成仍無實測依據。

本次沒有重跑189521筆全量交接、五來源原生讀回或先前TDCC缺件案例。後續應直接完成上述實作，針對改動部分測試，不以增加輪數或重跑舊PASS取代交付。

執行：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40857674847 。
