# JARVIS 原始數據整批驗收與正式上線紀錄

日期：2026-10-27（臺灣）；狀態核對時間：2026-10-27T20:21:17.988018+08:00

## 已完成

- 正式庫基底完整769項測試；整合後794項全部通過，0失敗、錯誤、略過。並非將舊候選233項重複加總。
- 本機Python3.12與GitHub Python3.11均通過；PR及主線雲端工作皆成功。
- 216個既有Python檔與154個既有工作流語法檢查，另驗證新增整批工作流（共155個）。
- PR #26已合併；正式程式commit：17d33f49ebee1aca9ffac3ae9b3c41e3317947ca。
- 四條既有官方修補工作均已進入Audit saved RAW and repair missing or invalid official units；checks及前批交接成功。此為啟動確認，不是整批下載完成。

## 此次實際修正

前導零與未核准商品不再被靜默略過OHLC；補足融資融券短欄位、百分號與缺值檢查；檢查清單只宣告實際執行的項目。舊版通過結果在新計畫下逐批本機重驗，讀回或解析失敗時保留原件、保留次數並禁止因此重下載。

2000至2012年財報送往compare/report的工作，列歷史路由待核，保留期別與缺口。官方說明：https://mopsfin.twse.com.tw/terms，提供各公司採用IFRS後財務資訊，起點與公司例外不同；此隔離規則不代表該年沒有財報。2013以後公司的實際採用年度、季度及舊制端點仍需資料驗收。

正式Drive.put接入財報轉換的模擬API測試確認：同一原件連跑兩次只create一個物件；建立成功但回覆遺失可讀回調和，不盲目重傳；內容衝突與損壞不覆寫。這是軟體接線驗證，不是宣稱所有真實遠端併發情境均已完成。

## 剩餘工作與邊界

6965項歷史財報路由待核（其中3649已存待驗證）、七大來源歷史母體、完整數值／口徑／PIT與遠端端到端復原仍未全數完成，詳見上線與剩餘資料工作總表.csv。資料庫完整性仍UNKNOWN。本輪沒有因測試通過而關閉資料缺口。

測試階段市場下載0；上線後由既有排程執行補抓，實際下載及補正數以各工作紀錄為準，不與測試項數混算。成功原件保存與缺失追蹤規則持續適用。

## 可查詢紀錄

- PR：https://github.com/danny541690/C1-RAW-DOWNLOADER/pull/26
- PR雲端驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40502742358
- 正式主線驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40502833198
- 新版四排程：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40502833143
- 後續scripts、tests、依賴及整批工作流變更，由jarvis-raw-repair-onepass-20261027.yml集中驗證；未新增下載排程。
