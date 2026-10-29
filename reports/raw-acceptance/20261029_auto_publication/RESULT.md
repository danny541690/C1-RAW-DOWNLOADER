# 驗收紀錄自動保存與重送實測（20261029 R8）

工作40856240354：SUCCESS；真正遠端Git保存、Drive寫入與讀回通過。相同紀錄同一工作連續發布兩次，SHA與Drive file_id完全一致，沒有重複建立。測試版本cc4587fc4d60994b9b4af7a66c60cff7f22b128a，源站請求0、原始數據寫入0。此為紀錄傳輸測試，不是資料來源驗收。

實測紀錄SHA：75643658fdf4f54f863c7e8603352ece9e3a828bcfcfc675a5c404013b99daaf；Drive file_id：10g8wKjI2L8pR5TARpGAruTb0CliQ5gLq；保存於RAW管理目錄的RUN_40856240354-1-publication-probe。Git狀態：jarvis-source-preflight/record-40856240354-1-publication-probe/TWSE。完整輸出remote-results.json。

新增v093_acceptance_publish：先把設定目錄中的JSON/Markdown/測試log與來源程式SHA、run/attempt/job、原job結果寫到Git，才呼叫Drive；寫入後實際讀回SHA。Drive失敗會留下Git的DRIVE_PENDING與安全錯誤分類，重新發布相同身分與內容可補傳；同身分改內容拒絕覆寫。每個工作分開命名，多來源/多方向的結果不互相覆蓋。限制單檔700KB、總量10MB，超出明確報錯而非截斷。

本機132項合併回歸通過，12份唯讀預覽設定檢查通過。新增單元測試證明：Drive存檔後中斷仍保有Git結果且可重送；錯誤讀回不能標記成功；相同身分改內容不能蓋掉舊紀錄；原始job的failure不會因發布成功改成success。故障情境為本機注入，真實遠端實測範圍是正常發布與同內容重送。

已接線的四份候選驗收流程：

- jarvis-seven-native-reuse-test.yml：5來源各工作結束時保存。
- jarvis-seven-import-test.yml：7來源save及verify各工作結束時保存；另補Drive發布所需的鎖定依賴安裝。
- jarvis-seven-closed-loop-batch.yml：start/resume各工作結束時保存。
- jarvis-seven-tdcc-missing-test.yml：start/resume各工作結束時保存。

以上均設if: always()，並使用實際job.status。已通過的舊來源案例本次沒有重跑；僅調整其未來執行時的紀錄步驟。四個既有流程修改後尚未各自重跑，不能宣稱所有hook在每種失敗環境已完成遠端驗收。checkout或依賴安裝失敗時仍可能無法執行發布步驟；Git亦不可用時會明確失敗，不會假稱保存成功。DRIVE_PENDING尚無另設背景補傳排程，須同紀錄重送或後續對帳補傳。

自動保存範圍目前限候選分支上述四份流程，不包含正式12份預覽入口、所有舊工作或歷史紀錄補傳。管理總表/registry本次仍由操作同步；新RUN紀錄會由上述流程自動發布，但不會自動把每條問題升格為修復或更新總表的完整驗收結論。

剩餘上線門檻仍是正式12入口與七來源下載/重用/補正/重驗的整合，以及來源共用配額/限流負載實測；正式入口須呼叫此發布模組。不能因紀錄保存測試通過就宣稱新12條已上線。

證據：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40856240354 。
