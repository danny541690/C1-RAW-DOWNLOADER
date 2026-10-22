# 第六條正式啟用：由新到舊對帳與已核准修復（2026-10-22）

使用者明確授權：第六條直接上線，從2026年10月最新可得資料往回至2000年1月修復。首次部署提交 b688e8aee7ac3ce42e81d550ef4895d9777b0c84。

正式流程為 .github/workflows/v093-v2-06-reconcile-repair.yml；每小時 UTC :15（台北時間亦為每小時 :15）觸發，工作流程期限75分鐘，獨立 RECONCILE 租約90分鐘。從保存的月份接續，完成一輪後由最新月份重新增量對帳，不將不存在的資料夾視為資料齊全。

第六條只改寫自己的缺漏帳本、修復任務與新修復產物；不改寫原始RAW或原隔離收據。修復由PRICE原有pool執行，與一般PRICE worker互斥；一般PRICE每次60分鐘預算內最多先用6分鐘處理修復。啟動時另執行6分鐘有界修復；第一輪若PRICE正執行，只在確認舊run已終止後退休其租約，不能以新owner身分借用舊鎖。其餘四條不取消或重設。

正式控制帳本：.github/live-state/stage06-live-control.json；月分片：.github/live-state/stage06-live-{stage}-{YYYY-MM}.json。公開帳本不放私人Drive檔案ID，RAW來源參照留在私人INPUTS檔案。候選檔先存至帶LIVE_REPAIR_ONLY及部署ID的專用資料夾，讀回核對後才以同一PRICE owner/fence的GitHub回執結案。舊隔離檔與原始RAW保留。

目前核准的自動修復是 TPEx indices、TWSE capital_reduction、TPEx ex_dividend；沿用已驗證的 NATIVE_INDEX_EVENT_REPAIR_V1，新INDEX/SECURITY與事件日期欄位保存於獨立staging格式。每個輸出都經原生座標與數值字串核對後存檔，仍不是數值口徑、PIT或分析發布核准。

其他處理類型產生BLOCKED_APPROVAL任務；身分不明保留IDENTITY_RECONCILIATION_REQUIRED；RAW雜湊不符交給RAW所有者的缺口，未知下載次數、交易日、範圍或來源相容性不得猜測。RAW自動補抓正式接點尚未開啟，不會在此版本新增市場HTTP下載。此版本不保證所有來源與所有欄位可自動修復，也不把掃過月份當成完整率。

本機完整回歸414項通過，其中本輪新增18項，涵蓋正式啟用授權、專用鎖、真實候選匯入與去重、舊收據不變、已結案不重開、未核准類型阻擋、RAW未知次數不猜測、身分精確對帳、正式Drive不可覆寫及價格切換的終止確認／新owner保護。

正式啟動run：[39727142058](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39727142058)。雲端414項回歸通過；2026-10完成對帳，建立16筆正式READY任務，原先3筆缺身分收據已由確切原RAW雜湊對帳。對帳斷點month_index=1，下一個2026-09。

截至2026-10-22台北時間13:21:18，正式任務8筆DONE、1筆CLAIMED、7筆READY，初次有界修復仍執行中。PRICE實際owner=39727142058/PRICE、fence=9，對帳用RECONCILE鎖已釋放。獨立讀回一筆TWSE減資輸出5972 bytes與驗證證據1378 bytes，其雜湊皆與GitHub正式回執一致；驗證核對2筆原生紀錄、10格。原RAW沒有修改，也沒有重新下載市場資料。

原有測試帳本16筆BLOCKED_APPROVAL繼續作歷史試驗證據，不把測試副本改成正式完成；本次正式缺口從現行RAW索引與隔離收據重新建立。

## 第一批最終結果

正式啟動run39727142058於台北13:23成功完成。雲端回歸414項全過；PRICE有界批次完成15筆、失敗0筆、因預算到期延後1筆。延後任務保留其不可覆寫候選檔與claim證據，claim到期後可由下一個PRICE owner接續，不重抓RAW。PRICE及RECONCILE租約均已釋放，last_fence分別9與1。對帳下一月仍為2026-09，後續修復先消化尚未結案任務。

同版本的獨立Drive整合run39727142016成功，完整回歸414項及原737格樣本整合通過。上述15筆是正式月分片的DONE，與舊TEST_NOT_LIVE帳本區別。這是三個已核准資料集的staging解析修復，不代表所有缺漏、數值口徑、PIT或分析資料已全面核准。
