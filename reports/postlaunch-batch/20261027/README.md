# JARVIS 上線後整批測試與首輪執行複核

日期：2026-10-27（臺灣）。完整測試801/801通過，新增7項；PR #27雲端及正式主線驗證皆通過，已合併正式主線（2236d893e5362d51f51211bce5867e5ca366f249）。

首輪正式run40502833143：四條工作全部success，未見Python traceback。工作次數合計：679次檢查、37次存檔讀回修補、72次原件重解析讀回；FinMind共69次請求、67次保存、2次失敗。不是唯一修復資料數，沒有據此結案。

2010-03工作進度實際列出20項UNRESOLVED_HISTORICAL_COMPARE_SCOPE，確認新路由隔離生效；不代表6965項已全部處理。FinMind的2次失敗只有計數證據，尚未讀取個別收據查明原因，保持待核。

本次發現與修正：新歷史財報隔離狀態未列入FinMind補缺GAPS，已接入既有有界補缺規劃，只針對明列公司／季別，不覆寫官方原件；來源／數值／PIT及官方缺口維持未驗證。任務鍵、配額版本與重試上限不變；已保存且讀回驗證的FinMind收據跳過不重抓。

大量blocked明細每45秒重印造成冗長紀錄。完整明細仍保存原本的FINMIND_GAPFILL_STATUS.json；console改列阻擋項數及原因次數，保留錯誤可見性。測試證明完整明細沒有被移除。

另外修正可重用測試器：記錄實際checkout commit及執行輸入SHA256，不再把舊版base commit當作每次測試版本。新增7項驗證：歷史路由補缺、收據鍵一致、合格與純品質問題不重抓、錯誤原件的公司表頭不能算數值覆蓋、已驗證補缺跳過、正確季度仍不自動驗收、縮短console但保留完整明細。

測試與程式上線不等於資料完整；全庫完整率仍UNKNOWN，原始盤點缺口與歷史母體、官方舊制端點、數值／PIT仍保持開放。

執行證據：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40502833143 。各工作末狀態及錯誤／阻擋分類見production_review.json與四排程首輪結果.csv。

## 新版交接後的實際複核

新版run 40509562994的checks、交接與四條修補工作全數success；未見Python traceback。工作計數合計：542次原件檢查、24次存檔讀回修補、73次重解析；FinMind53次請求、52次保存、1次失敗。這是執行次數，不是唯一缺口結案數。該次失敗的個別收據原因仍待讀取確認，不將失敗掩蓋成成功。

四條工作最後月份：RECENT_ASC 2018-07、RECENT_DESC 2022-12、EARLY_ASC 2003-02、EARLY_DESC 2010-02；為該批最後工作點，不代表該月完整。2010-02進度曾列189個歷史財報路由待核，數量只適用該月進度快照，不可當全庫缺口。四條工作的console都已改用blocked_tasks與blocked_reason_counts，完整明細仍保存在Drive原報告。

最新另一期四條排程run 40524439519在查詢時仍in_progress，本報告不提前計入成果。資料庫完整性、數值與PIT維持未核准；原先6965項歷史路由待核總表未因本次程式驗證而結案。

PR：https://github.com/danny541690/C1-RAW-DOWNLOADER/pull/27

PR雲端驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40509394148

主線雲端驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40509563051

新版四排程：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40509562994
