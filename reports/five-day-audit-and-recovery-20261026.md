# 排程1–6、5-1、6-1 五日問題查核與恢復（2026-10-26）

範圍：2026-10-22 00:00 至本次查核（Asia/Taipei）；另取得10/21前置紀錄作追溯。全庫1294筆為10/21–26 UTC擴大盤點，指定現行工作流431筆亦為擴大範圍，不冒充嚴格五日分母。36筆結論失敗執行的失敗job已讀取；4個期交所檔名型失敗沒有job（工作流程配置錯誤），失敗job詳列附錄。舊版本各種來源單元錯誤由既有查核報告補充；未保留的逐次訊息無法保證全數還原。工作流程成功不等於單元完整。

## 本次修正

- Google已由使用者切換正式模式並更新配對三項憑證。第38次第2次嘗試已越過權杖更新；仍以恢復工作流唯讀OAuth/原資料夾驗證作啟用門檻。
- GitHub CAS PUT遇500/502/503/504或傳輸中斷，先回讀確認是否已提交；未確認相同內容則交由原有界CAS循環重新載入，禁止盲目重播舊SHA。403權限錯誤仍立即停止。
- Drive僅對明確userRateLimitExceeded/rateLimitExceeded的403加入既有有限重試；一般權限403不重試。IncompleteRead納入讀取/保存後核對的有限重試。成功RAW不覆寫。
- 732項本地回歸通過，包含新增5項故障注入。下載來源、日期分區、成功收據與重試次數不重設。
- 恢復工作流僅啟用5個現行工作流程（共8條）；保留現存執行，取消已知過期等待run40206907842；不啟用舊RAW/轉換/壓力測試工作流程。沒有活躍批次才派發新批次。

## 問題分類與修正邊界

|類別|問題|處理／仍開放事項|
|---|---|---|
|共通|invalid_grant過期/撤銷、配對錯誤|新三項憑證；不再反覆生成token；正式模式不保證永不撤銷|
|共通|手動停用、取消、排隊不動|恢復白名單；保留活躍批次；舊等待批次取消；取消不自動算資料遺失|
|共通|GitHub PUT504、CAS衝突、過期租約|本次增加提交回讀；不刪鎖或強佔現行租約|
|共通|Drive讀取中斷、限流403|本次有限重試；持續失敗保留故障，不當成保存成功|
|1–4|403/429、DNS/逾時、空回應、404/路由未解析|現有共享限速/冷卻/缺口清單；未驗證替代路由不放行|
|1–4|財報批次companyId參數TypeError|既有表單修復；近期未復發，不等於缺RAW已補齊|
|1–4|缺少財報公司/報表組合未建任務|V8保留補建計畫，21請求對應417組合是工作量，不是下載成果|
|1–4|價格缺值/非交易、事件日期、未知數值欄位、會計/單位/PIT|品質開放；不補造OHLC或用檔名當公告日|
|5/5-1|IncompleteRead、cookie/session失效、HTML版型、日期/證券未確認|既有會話重建、有限重試、結果區嚴格驗證|
|5/5-1|空JSON/查無資料、目前證券候選非歷史全集|保留原證據；候選4100不等於歷史全市場|
|5/5-1|週查詢未提供2000至2025-10-30|保留未提供區間，需其他官方歷史檔案；無法靠重跑補造|
|5/5-1|摘要寫入過密/游標落後/儲存錯誤混作來源限流|既有逐日帳本回讀、30秒摘要、按request_phase分類；本次Drive容錯補強|
|6/6-1|520/502/503/504、來源探索逾時、Swagger HTML|既有已驗證官方鏡像、配對入口、主機冷卻、到期舊故障優先|
|6/6-1|API原生CSV卻只按JSON、期權欄名、DOS EOF、註腳、雙表頭母子列|現有嚴格原生格式解析；未知格式不任意放寬|
|6/6-1|Delta公布日/到期日、夜盤日期、未來連結|分別保留真實時間語義，不臆造來源日期|
|6/6-1|兩端表單目錄不齊、別名重抓|V6同步14個驗證表單、同條件同SHA配對才復用|
|6/6-1|中斷快照無RAW、最新API不能重建舊快照|MISSED_SNAPSHOT保留；後續成功快照不冒充舊日還原|
|6/6-1|舊欄位None造成統計TypeError|既有V6.1布林統計修正且測試已通過|
|6/6-1|冷卻後空轉、逐筆頁失敗卻標完成、進度混入另一端|既有短冷卻等待、失敗有限重試、分列分區與未嘗試|
|資料品質|保存SHA、數值語意、PIT、全市場涵蓋率|四者分開，尚未全面驗證；沒有證據不能宣稱全正確|

## 工作流程盤點（擴大窗口）

|工作流程|總數|成功|失敗|取消|其他|
|---|---:|---:|---:|---:|---:|
|v093-official-four-lane-repair.yml|38|27|5|4|{'pending': 1, 'in_progress': 1}|
|v093-taifex-independent-asc.yml|90|73|8|9|{}|
|v093-taifex-independent.yml|128|90|10|28|{}|
|v093-tdcc-independent-asc.yml|78|41|7|30|{}|
|v093-tdcc-independent.yml|97|65|6|26|{}|

## 失敗job證據（每次執行最新嘗試；非錯誤次數）

- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39982006903/job/120511414420: 2026-10-23T15:53:45.9432608Z TimeoutError: The read operation timed out
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40135548495/job/120996186332: 2026-10-24T21:45:07.4667382Z TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'; 2026-10-24T21:45:07.4678232Z TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40135548565/job/120996186440: 2026-10-24T21:46:43.2976521Z TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'; 2026-10-24T21:46:43.2981150Z TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40129604648/job/120978385650: 詳見job原始日誌
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40116000096/job/120937386142: 2026-10-24T17:43:28.0463818Z http.client.IncompleteRead: IncompleteRead(0 bytes read); 2026-10-24T17:43:28.0507599Z http.client.IncompleteRead: IncompleteRead(62533 bytes read)
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40209800280/job/121218398729: 2026-10-25T16:03:10.5815900Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T16:03:12.6642340Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40209675995/job/121218017400: 2026-10-25T16:01:33.1066735Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T16:01:35.0951785Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40209319650/job/121216963357: 2026-10-25T15:57:01.1811071Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:57:03.2101000Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40208723026/job/121215163093: 2026-10-25T15:49:25.9928145Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:49:27.9809756Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40207578685/job/121211716906: 2026-10-25T15:34:45.2702471Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:34:47.3145316Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40207427159/job/121211252014: 2026-10-25T15:32:51.9881289Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:32:53.9635672Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40206725169/job/121209132434: 2026-10-25T15:24:06.6600145Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:24:08.6661606Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40205764346/job/121206234398: 2026-10-25T15:11:53.2727093Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:11:55.8950519Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40205514352/job/121205466910: 2026-10-25T15:08:37.3951989Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:08:38.9097540Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40205192320/job/121204507721: 2026-10-25T15:04:37.0557817Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T15:04:39.0287439Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40204562200/job/121202628611: 2026-10-25T14:56:39.8986699Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:56:42.4497547Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40203975301/job/121200862201: 2026-10-25T14:49:01.6322819Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:49:03.2232648Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40203610373/job/121199776881: 2026-10-25T14:44:15.8478871Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:44:17.8039833Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40203137655/job/121198364300: 2026-10-25T14:38:21.2538575Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:38:22.9069931Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40202190813/job/121195581617: 2026-10-25T14:26:22.3910154Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40202190813/job/121195581661: 2026-10-25T14:26:23.6490818Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40202190813/job/121195581674: 2026-10-25T14:26:19.7222875Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40202190813/job/121195581828: 2026-10-25T14:26:20.5822607Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40202110407/job/121195269303: 2026-10-25T14:25:08.5385933Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:25:09.8610027Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40201290460/job/121192823868: 2026-10-25T14:14:35.3519114Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:14:36.8013809Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40201066070/job/121192154808: 2026-10-25T14:11:45.7203028Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:11:47.8317282Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40200934575/job/121191771216: 2026-10-25T14:10:04.2499145Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T14:10:06.6174715Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40199946834/job/121188805029: 2026-10-25T13:57:19.3160176Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T13:57:21.1155152Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40199642133/job/121187876974: 2026-10-25T13:53:11.9529346Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T13:53:13.3360101Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40199410557/job/121187181925: 2026-10-25T13:50:13.6741666Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T13:50:15.4282134Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40199145533/job/121186373319: 2026-10-25T13:46:48.4691143Z {"key": "HISTORY|bargainOrderDown|2015-12", "status": "UNRESOLVED", "error": "TimeoutError:network read timeout"}; 2026-10-25T13:46:50.3522198Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197934581/job/121182833284: 2026-10-25T13:44:30.7736395Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:30.7766862Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197934581/job/121182833330: 2026-10-25T13:44:26.5057396Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:26.5083543Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197934581/job/121182833333: 2026-10-25T13:44:23.8234464Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:23.8281614Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197934581/job/121182833357: 2026-10-25T13:44:20.6618869Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:20.6654105Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197358144/job/121181003920: 2026-10-25T13:44:19.8650750Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:19.8684350Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40197271730/job/121180850172: 2026-10-25T13:44:20.5255264Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}); 2026-10-25T13:44:20.5287144Z google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40176699067/job/121118897476: 2026-10-25T08:42:14.2493042Z TimeoutError: timed out; 2026-10-25T08:42:14.2527153Z TimeoutError: timed out

## 既有詳細逐類報告（保留原時間快照，不當作今日累計）


### official-v6-problems-and-release-20261024.md

# 排程一至四：未解決問題與V6修正

## 查核範圍與限制

2026-10-24約20:21至20:25（台灣時間）讀取四路RETRY_MONTHS及其16個月份的OFFICIAL_REPAIR_STATE，包含2000-01..05、2012-10..12、2013-01..03、2026-06..10，共5,680個月份／單元狀態。這是已追蹤月份的快照，不是2000至2026全期間的缺漏總數；不同月份讀取時間略有差異。舊error欄位可能保留於後續成功紀錄，不能將所有error文字再加總為現存錯誤。V6依當前status分類，保留原有error供追溯。

| 當前狀態 | 快照單元數 | 解決方案與V6行為 |
|---|---:|---|
| 官方明示歷史期間不提供 | 628 | 保留起始日期證據；尋找其他官方歷史檔，不製造資料、不繼續打相同已知無效期間 |
| 來源回覆無資料，原因未確認 | 1,354 | 與歷史不提供分開；查交易日、上市狀態與事件範圍；V6延後24小時重訪，不把空回應認定為完整 |
| 共享請求時窗等待 | 121 | 不計來源呼叫與嘗試；繼續其他單元 |
| HTTP 404官方路徑失效 | 17 | 保留紀錄；需驗證官方替代路徑，不能以猜網址或第三方內容冒充 |
| 官方路徑未解析 | 466 | 有RAW先做本地查核；缺RAW才需修復對應官方路由 |
| 本地內容已查核但品質仍開放 | 1,425 | 保留RAW與SHA；數值規則、停交易／缺價、事件與PIT分項待驗證 |
| 來源已取得但品質仍開放 | 49 | 不重抓已保存內容；針對剩餘會計、單位、歷史公司範圍及PIT工作 |
| 來源退避／熔斷 | 908 | 與實際403、429分開；V6暫時傳輸失敗共用120秒冷卻 |
| 實際來源存取受阻 | 36 | 快照為TPEx HTTP403；V6四路共用1小時來源冷卻，保持本地查核運作 |
| 單點嘗試耗盡／時限待重試 | 35 | 保留嘗試與週期；不因換版清空當前重試上限 |
| 重試週期耗盡 | 160 | 有RAW可在V6一次離線回查；無RAW保留補下載缺口，不能宣稱解析完成 |
| 來源內容缺少要求公司／期間 | 27 | 檢查歷史公司名單、報表期間及端點接受範圍；不可刪掉缺少公司以通過 |
| 舊RETRY_LATER／基本通過仍需檢查 | 23 | 隨游標重新查核及分類，保留原始證據 |
| 內容層檢查通過 | 431 | 保留並跳過；不是數值語義或PIT完整驗收 |

## 具體錯誤及仍需完成的工作

- `TypeError:not a valid non-string sequence or mapping object`：已修正保留重複companyId的表單參數；近期紀錄未見復發，不代表所有缺漏已重新取回。
- `TimeoutError`、DNS `URLError`、`IncompleteRead`：V6加入共享冷卻，維持既有有上限重試；沒有收到回應時只存在失敗紀錄，不能算RAW已保存。
- `EVENT_PERIOD_UNPROVEN`：事件表日期未獲證明；需以原始內容欄位建立日期規則，不能只以要求月份或檔名補日期。
- `NO_REVENUE_TABLE`：需要官方營收HTML樣本／版型辨識修正；保留原始回應與SHA。
- `EMPTY_SECURITY_IDENTIFIER`：需判斷是否官方合法摘要列；只接受已證明的版型，不能全面放行空代碼。
- `NON_NUMERIC_CELL:*%`：V5已處理明確持股比例欄位的百分號；仍殘留的舊錯誤由當前status判斷，不能全算新錯誤。
- `HOLDING_PERCENT_OUT_OF_RANGE`：需核對欄位定義及官方值；不放寬0..100或默默截斷。
- `PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED`／`NO_VALID_TRADE_PRICE_REQUIRES_REVIEW`：與來源無資料分開保留，仍須交易日與證券狀態佐證，不補造OHLC。
- `NUMERIC_FIELD_RULES_NOT_COVERED`：尚無欄位級驗證規則；需要逐資料集補規則。
- `FINANCIAL_ACCOUNTING_IDENTITIES_AND_ANNOUNCEMENT_TIME_NOT_PROVEN`：會計恆等式、原始單位、累計／單季及公告時間未證明；重解析回讀不是會計語義或PIT驗證。
- SHA／回讀不一致：是獨立失敗分類；V6保留舊有效收據，不能把失敗替換算成功。近期已完成三、四job logs未觀察到此類錯誤。

## 六月300個MOPS財報特別查核

22:45追蹤結果：213個完成既有RAW重解析及解析輸出遠端SHA確認，87個重試耗盡。MONTH_STATE顯示前述87個當時為RETRY_WAIT且沒有evidence_file；沒有可用RAW，因此不能靠離線重解析完成。四個另新增的MOPS營收單元不納入這300個財報分母。原始檔重新下載替換並回讀確認為0，全品質驗證完成為0。

## V6實作與驗證

Execution revision：`OFFLINE_RECOVERY_AND_SHARED_SOURCE_COOLDOWN_V6`。QUALITY_REVISION維持V4，避免對相同已驗證RAW全面重開。

1. 原來終止的單元若仍有RAW，可一次離線回查，不重置當前來源嘗試／週期，不重複已完成的本地品質查核。離線失敗保留原始終止狀態，不偷偷增加網路重抓。
2. 403／429四路共用來源冷卻1小時；暫時傳輸失敗共用120秒；來源空回應延後24小時重訪。既有共享請求時窗、月份鎖與相遇暫停保留。
3. 每月處理結束或批次時間到時寫入 `OFFICIAL_UNRESOLVED_ITEMS.json`，附問題分類、下一步、原始／解析SHA、嘗試與品質待驗證項目。這份清單是當月快照，不冒充全庫驗收。
4. 實際收到但驗證未通過的回應，記錄 `REPAIR_EVIDENCE`位置及SHA；成功RAW維持不可變。

本地完整測試659項通過，涵蓋既有6個合成月份四路頭尾相遇、暫停、續跑、重試與RAW不重抓整合流程。合成流程不是全市場資料正確性證明。新增測試涵蓋共享冷卻、冷卻不縮短、離線恢復不重置來源上限、失敗不觸發新下載及問題分類。會計與PIT驗證門檻仍未完成，不能宣稱所有問題已排除。

## 證據

- 六月狀態：https://drive.google.com/file/d/1XtBuaI0TihyvF9c5VScBZfPP_sbr3Yfo/view
- 六月原始收據：https://drive.google.com/file/d/1Un-Wm_23muhcpkgRUAvxmyiU1vTfK_fW/view
- 八月狀態：https://drive.google.com/file/d/1UJxB2vPmYHRtYjR0eWtiUJdsrB2itumw/view
- V5最新追蹤批次：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40102429784



### official-v8-missing-unit-repair-20261025.md

# 排程一至四：缺漏下載與資料修補 V8（2026-10-25）

## 查核結論

四個排程有持續運作，既有程式也具備下載、內容查核、保存及遠端 SHA 回讀流程；但缺漏任務規劃有具體漏洞。完全不存在於原本 financial_units 的財報公司／報表組合，未加入日資料規劃產生的候選清單。2013-06 MONTH_STATE 實例有 222 個財報紀錄，官方保存資料可辨識 1,603 個公司代碼；重算得到 417 個未建任務的公司／報表組合。V8 合併為 21 個請求。這是新建下載工作量，並非已下載成功數；歷史公司全集仍待核對。

## V8 修改

- 季底月份從官方保存資料的公司集合補建缺漏財報工作；合併每批至多 20 公司。
- 下載計畫保存至 OFFICIAL_REPAIR_STATE.json 的 financial_plan_jobs，跨批次沿用相同 unit_id，不重建失敗工作以繞過重試上限。
- 既有工作、正確原始檔及失敗重試歷程保留；部分公司缺漏仍由原單元列為品質問題，不能當作完整。
- 各排程已走過月份加入一次性計畫核對佇列，不倒退前緣游標；未完成月份保持待處理標記。每批最多 180 秒回補歷史佇列，其餘預算繼續前進。
- 舊 CONTENT_CHECK_PASS 只有在 RAW 檔案參照、SHA 與保存狀態均存在時才能直接跳過；缺失保存資訊者重新補下載。
- 新下載財報在遠端 RAW SHA 回讀成功後，同次立即解析並保存／回讀衍生檔。解析失敗保留有效 RAW、獨立列錯，不重抓相同來源位元。

## 兩天內已確認的動作與問題

已保存並回讀的新原始檔：2013-06 財報 5、2013-07 TPEx 借券 1、2013-09 財報 24、2013-10 TPEx 市值 1、2013-12 TPEx 價格 1，共 32。此為先前逐單元 SHA 證據確認的成果，不累加各批 STATUS 計數；不是全資料庫總成功數。

2026-06 原 300 個 MOPS 問題單元：213 已重新解析並確認衍生檔 SHA；86 來源退避、1 重試週期耗盡。原參數 TypeError 在最新這 300 筆 error 中未復發。213 是解析修補，不是重新下載 RAW，且會計恆等式、單位、公告時間與 PIT 尚未全數驗證。

- 官方來源空回應：保持 SOURCE_NO_DATA_UNCONFIRMED；無資料與休市不能自行混為一談，冷卻後重試。
- 官方明示歷史不提供：OFFICIAL_PERIOD_NOT_PROVIDED，獨立列缺口，不冒充補齊。
- 官方來源 403／429：共享來源限速、退避及重試上限；仍可能未解，不能承諾下載到官方不回傳內容。
- 來源路徑缺失／404：獨立列 OFFICIAL_ROUTE_NOT_FOUND／UNRESOLVED_OFFICIAL_ROUTE；不以空檔替代。
- 價格缺值／非交易狀態、通用數值規則未覆蓋、財報會計與 PIT：保持品質待驗證；不因此覆寫正確 RAW。
- Drive IncompleteRead：run 40116000096；SHA 回讀中斷不是已確認 SHA 不一致，後續批次已恢復。
- Drive userRateLimitExceeded：run 40129604648；這是 Drive 控制檔寫入配額，與官方資料來源限流分開；後續批次已恢復。

## 上線前最新批次基線

讀取時間約台北 2026-10-25 09:45，run 40150902971 四個工作均仍執行中；下列為該批快照，禁止當成歷史累計或各月總數。

| 排程 | 正在處理月份 | 本批檢查 | 本批 RAW 補正成功 | 本批來源呼叫 | 本批已取得回應 |
|---|---|---:|---:|---:|---:|
| 1 | 2001-05 | 22 | 0 | 69 | 69 |
| 2 | 2011-10 | 45 | 0 | 40 | 40 |
| 3 | 2014-09 | 236 | 0 | 19 | 19 |
| 4 | 2025-08 | 3 | 0 | 29 | 27 |

排程三該批已確認 88 個財報解析檔的回讀。任務完成、掃過月份、取得 HTTP 回應與 ZIP 保存，都不代表完整正確。

## 驗證

完整測試包含四排程月份租約、相遇暫停／存活者完成、斷點續跑、缺失下載、舊 RAW 保存、遠端 SHA 不符回滾、財報任務去重與重試歷程保存、新 RAW 立即解析、解析失敗保留有效 RAW。部署後必須再確認 checks 與四個實際 job，不以合併成功代替上線成功。

## 證據

- 最新基線執行：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40150902971
- 2013-06 原始月份狀態：https://drive.google.com/file/d/1QGXPmJ_mT-DCddDU7H5FV9fiuh-4Rf1f/view
- 2026-06 修補紀錄：https://drive.google.com/file/d/1XtBuaI0TihyvF9c5VScBZfPP_sbr3Yfo/view
- 過去盤點：reports/official-v7-integrity-speed-plan-20261024.md（2026-10-24 快照，不冒充目前完整盤點）。



### tdcc-three-day-error-review-v7-20261025.md

# 集保所排程五與五之一：2026-10-23～25查核與修正

查核範圍為保留的Drive日期帳本、既有修復報告與GitHub近600筆工作流程中的165個TDCC批次（最早2026-10-23 15:26 UTC）。快照為110成功、52取消、2執行中、1等待；取消不自動視為下載錯誤。單元失敗可能被程式捕捉，所以workflow成功不能證明無單元錯誤。這不是每次已消失錯誤的完整歷史次數。

已跑完候選清單：2026-10-16 保存4088/空12；2026-10-08 保存4070/空30；2025-10-31 保存3764/空336；2025-11-07 保存3767/空333。每日期4100候選，並未證明歷史股票母體完整。2026-10-22以整批快照保存，不能加入逐檔單元數一起當獨立完整數。

查核時10/2帳本保存1312、空4、UNRESOLVED 1(IncompleteRead:65520 bytes read)、REQUEST_INTENT 1；11/14保存353、空52、REQUEST_INTENT 1。讀取期間帳本持續變動，不累加成三日成功總數。

|問題|原因與處理|尚未解決界線|
|---|---|---|
|讀取逾時、IncompleteRead、會話中斷|既有限重試與優先重試；V7新增IncompleteRead重建官方cookie/session|不得當作空資料|
|官方查無資料、空JSON|保留來源原始證據、分類SOURCE_EMPTY_UNCONFIRMED|不是歷史不存在的證明；成功與空回覆分開|
|日期或證券代碼未確認|檢查真正結果區而不是下拉選單回顯|不接受別日或別股資料|
|HTML表格、調整列格式|辨識持股分級表、列結構及非負股數、調整列|未知表格繼續列報，不任意跳過|
|候選代碼空白與歷史股票母體|先前版本修正去空白；歷史母體仍基於目前候選|不能宣告4100候選等於所有歷史證券|
|2000至2025-10-30未列於官方週查詢|依官方選單範圍繼續；不生成虛構查詢|需要其他官方歷史檔案，程式無法補造|
|未嘗試被誤讀為錯誤|V6分列not_attempted/failed/interrupted|待處理不等於全都下載失敗|
|重啟斷點落後與控制寫入成本|逐日期帳本立即保存、回讀；摘要30秒合併，重新載入最新帳本|成功原檔不重抓不覆寫|
|Drive保存/回讀403被誤分類成來源限流|V7依request_phase分離STORAGE_OR_READBACK_ERROR與SOURCE_BACKOFF|原始錯誤與儲存錯誤分開|
|保存錯誤證據再次失敗|V7保留evidence_save_error，繼續記錄原始錯誤|Drive完全不可寫時仍可能無法持久化|
|SHA不一致|保留READBACK_MISMATCH類別、禁止覆寫|本次沒有證據證明已發生實際SHA不符|
|數值/PIT|保存原生資料，numeric_verified/pit_verified保持false|未完成全面語意及時間驗證|

V7不更動日期分工、不重設下載進度、不刪除原檔、不因換版本重設成功狀態或擴張官方歷史提供範圍。

證據：Drive五控制目錄 https://drive.google.com/drive/folders/1S-IwCfV7goW5o6zHvrNHI-Qg_NoX_XbA ；五之一 https://drive.google.com/drive/folders/1X8XuUhbVRSAj5vmIZitN2Q5r-f_9emrG 。



### taifex-v6-two-day-problems-20261025.md

# 期交所排程六、六之一：10/23–10/25問題總表與V6發布

僅限TAIFEX，不包含三官方排程1–4。以現存日誌、逐單元憑證、兩端目錄與真實原檔重播查核；未留存日誌不能保證追溯。下表涵蓋已辨識問題類型，錯誤次數不跨批重複累加。

## 目前留下的錯誤與新發現

V5.1基準：排程六128筆UNRESOLVED，126筆Swagger、1筆2017-01 productOrderDown HTTP520、1筆2026-10-23中斷快照。126筆Swagger涉及121個不重複URL，不是126類全部缺歷史資料。六之一未解決下載錯誤0，但僅有9個表單，六已探索23個；因此先前的0錯誤並不代表全部可查項目已下載。

V6驗證同步14個官方表單定義。每份核對官方來源頁、action、查詢參數型態與日期上下界；保留既有表單與成功憑證。六之一以同語意入口去重後，計畫從649變為1429個歷史單元，其中780個尚未嘗試。這是查詢計畫，不是聲稱官方有780份實體檔，也不含已超出官方明示提供期間的資料。

## 兩日問題、處理及未解決界線

| 問題 | 已有修正／V6追加 | 仍須保留的限制 |
|---|---|---|
| 啟動、探索來源頁逾時 | 驗證過的目錄可繼續；探索有上限 | 網頁暫時不能取回不代表資料不存在 |
| HTTP520、502/503/504、連線逾時 | V4有限三輪、每輪三次且冷卻，不跨版本無限重設；V6擴充已驗證官方替代入口 | 短暫來源故障仍可能復發 |
| 六之一只有9表單、六有23表單 | V6同步14個安全驗證的官方表單，重新從2000-01補新增查詢計畫 | 部分表單只有近年區間，不能擅自伸長 |
| 相同項目多入口重抓 | V4三組入口配對238組不重複SHA一致；V6追加商品成交117、單式10、組合式3組相同SHA配對 | 只有白名單且相同期間、非空參數才去重；不同商品篩選不可合併 |
| 舊失敗已有另一入口成功檔 | 遠端回讀SHA、日期、格式、查詢條件相符後恢復原失敗憑證 | 共用檔不叫新增下載，不改寫成功檔 |
| 官方API回傳Swagger | HTML拒收、24小時路徑冷卻；保留錯誤；可下載的官方歷史CSV與年度ZIP繼續 | 不能保證121個URL都能由公開替代源完整取代；不假造成功 |
| API回CSV卻只解JSON | V5/V5.1四個已實測入口支援原生CSV或JSON，CSV保留.csv與原SHA | 未知入口、錯表頭、欄數或日期不符仍拒收 |
| 期貨與選擇權欄名不同 | 四個API入口全部按實際原檔表頭逐欄驗證 | 期貨契約代號、合計成交量、未沖銷契約數不可套用選擇權欄名 |
| 年度CSV尾端0x1A | 只在EOF容忍已知DOS控制字元；原bytes保持 | 檔案中段異常仍拒收 |
| 大額交易人CSV註腳與期權不同表頭 | V3/V3.1白名單註腳與表頭 | 未知註解、註解後仍有資料拒收 |
| 組合式鉅額交易雙表頭／母子列 | 母子序號、腿數、母列日期核對 | 缺列、錯配不能略過 |
| Delta公布日與契約到期日不同 | 使用官方公布日期，另留到期日 | 抓取日期不冒充資料日期 |
| 日期格式、夜盤歸屬 | 民國／西元及壓縮日期辨識，保留交易時段 | 不把夜盤實際時鐘日任意改成交易歸屬日 |
| 官方明確查無資料／空CSV／404 | 留證、區分來源空回覆與網址未提供、繼續其他單元 | 不補零，不證明永久歷史不存在 |
| 逐筆歷史窗口與付費歷史 | 只抓公開近期連結；各表單依官方區間；優先公開年度ZIP | 逐筆僅近30交易日；申購資料未擅自購買 |
| 逐筆頁失敗被標成當天完成 | V6只有成功才標當日完成；失敗每15分鐘有限重試、每天最多3次；主機冷卻不消耗每日嘗試 | 頁面長期不可達仍待查，不能當沒資料 |
| 未來檔案連結 | 排除未來日期 | 網頁列出不代表已發布可用 |
| 中斷REQUEST_INTENT | V4標中斷待確認，保存嘗試數；V6把舊日期快照另列MISSED_SNAPSHOT_CAPTURE_NOT_RECREATABLE | 2026-10-23未保存的快照不能用今天最新API回覆重建 |
| 控制寫入拖慢 | V6只有STATUS摘要每30秒更新；每次請求意圖、結果CURSOR仍立即持久化並回讀；結束強制更新摘要 | 不移除RAW回讀或主帳本安全檢查 |
| 匯入另一端成功量造成進度誤讀 | 分開本分區、匯入／區外、獨立檔案數；V6增加計畫數、未嘗試數、空回覆數及獨立故障URL數 | 掃到月份或0下載錯誤不等於完整涵蓋 |
| 保存SHA／數值與PIT | 原檔不覆寫；雜湊不符隔離；數值與PIT保持false | 格式／傳輸正確不是所有金融數值語意驗證完成；無證據顯示本案已發生真實SHA不一致 |

## 本次真實來源實測與驗證

2017-01商品成交productOrderDown與dlProductOrderDown兩個官方POST，皆取得593 bytes、10列、日期2017-01-12..17，SHA1995f1e8f171b4955f8d25a92480444122bae9d95c5ef22afd86c9e94c832a33。這是本地實測；正式恢復要看新版run的Drive保存／SHA憑證。

保留前版已確認成果：六恢復14個對應官方入口憑證；六之一5個舊520單元從保留RAW恢復；四個API原生CSV（期貨2146、選擇權11302、匯率35、法人期貨66列）均已正式保存回讀。不可在每個新批次再累加為新增成果。

V6完整695項測試通過，含目錄來源／參數／日期安全、ASC分區、入口去重保留成功／空回覆／既有失敗次數、逐筆頁失敗重試、主機冷卻與摘要節流，兩端工作流程上線後各自再次執行全庫測試。

官方參考：https://openapi.taifex.com.tw/ 、https://www.taifex.com.tw/cht/3/productOrderView 、https://www.taifex.com.tw/cht/9/tradersQAIS 、https://www.taifex.com.tw/cht/3/futContractsDateView 。官方提供不同項目與期間，不存在統一2000年起全項目免費歷史的保證。

V6.1雲端驗證補充：V6的摘要統計對舊UNRESOLVED紀錄缺少interrupted_request時，sum收到None而使六中止（run40135548495）。CURSOR已持久化，六之一已開始新增表單補查。修正為明確布林計數，追加缺欄與null測試，且以實際DESC舊帳本重播save；完整696項測試通過。此為摘要錯誤，不是來源資料或SHA不一致。



### taifex-route-recovery-v8-20261025.md

# 排程六／六之一 V8：Swagger、遺失快照、HTTP 520

## 查核基線

2026-10-25 06:11，DESC CURSOR：126個Swagger失敗快照、1個中斷快照、1個2015-12 bargainOrderDown HTTP520。這是保留的失敗紀錄，不等同126個目前完全不可下載的資料集。按官方邏輯URL比對，116個失敗快照所屬資料集已有後續保存及遠端SHA確認；尚無任何成功快照的只有5種路由、合計10個舊失敗快照。後續成功不能重建舊日當時的快照。

## 已實測並加入的四個官方CSV入口

|資料|官方目錄|列數|原生內容日期|
|---|---|---:|---|
|每日Delta|https://data.gov.tw/dataset/11321|8334|CSV沒有公布日期；契約到期日不能當資料日|
|調整開盤參考價|https://data.gov.tw/dataset/136666|72|2026-09-23～2026-10-22|
|盤後調整開盤參考價|https://data.gov.tw/dataset/157963|15|2026-08-21～2026-09-16|
|盤後豁免／非豁免商品|https://data.gov.tw/dataset/170553|26|2026-10-23|

原始下載URL均由官方目錄連結確認，為https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=對應路由。SHA及容量見taifex-v8-live-probes-20261025.json。

Delta精確檢查6欄、契約唯一鍵、合法月份及W/F週別、有限數值、Delta[-1,1]與到期日格式。原始CSV不改寫，content_period=null、publication_date_verified=false，不臆造公布日期。其餘3項嚴格驗證實際日期與原生欄位。僅限當日捕捉；先前成功檔不重抓。

CCP_CMLists官方目錄https://data.gov.tw/dataset/170552指向同類CSV入口，但兩次本地實測逾時；尚未納入未驗證的CSV解析規則，保留待處理。

## HTTP 520

2015-12 bargainOrderDown的官方替代入口dlBargainOrderDown實測取得308 bytes，兩組交易、4個子單，實際日期2015-12-08～15，SHA f91456f108a370b7df55e9410962916f61dc92accb8d583f76d754637fc42d7a。這個替代入口已有同內容驗證與程式支援，V8新增「到期傳輸錯誤優先處理」避免等新月份掃完才回補。

連線型錯誤重試間隔由15分鐘改為60秒，仍遵守來源主機冷卻、分區、SHA保護及最多3次×3輪；403/429限流仍15分鐘。每批最多優先4個舊傳輸單元，繼續其他資料。單元重試與來源主機冷卻分開，已存成功單元完全跳過。

## 中斷快照

2026-10-23 BlockTradeContinuousMatchingSingleOrder只留下REQUEST_INTENT，沒有原始回應或SHA。已有2026-10-25後續快照保存且SHA確認，其實際來源內容日期為2026-05-28；不可以把它改名為10/23當時快照。V8在OPEN_ITEMS列出後續可用檔與SHA，但保留original_capture_recreated=false及原中斷缺漏。另外實測官方歷史表單查2026-10-23亦逾時，尚未取得該日歷史內容，保留缺漏。若後續取得則另存為歷史資料，不宣稱還原當時API回應。

## 上線與驗證範圍

兩排程共用V8程式，DESC處理2013年至最新、ASC處理2000～2012。新增故障重試優先處理與路由健康摘要。歷史失敗數、已有後續成功數、仍無成功路由數分列；原始失敗紀錄不刪除，不把數字變小當資料補正。

706項整合測試通過（發布前最後驗證仍須以實際測試輸出為準）。保存、遠端SHA、數值/PIT、歷史涵蓋率仍分開；本地取得回應不算Google Drive保存成果。

## V8.1後續實測更新

CCP_CMLists兩次逾時後，使用一般瀏覽器User-Agent與官方Referer的新連線成功取得原生CSV，2048bytes、33列、2026-10-23，SHA 57ca175bebb52e21c3f02373db27c7ec244014b3f3134d64665be8cf443499af。已加入精確三欄解析與官方目錄映射，優先捕捉；先前逾時並非無資料。原四份CSV在V8正式排程40137877128均已保存並遠端SHA確認。V8.1保留這四份成功檔，不重抓。

## V8.2短冷卻恢復

V8.1實際執行遇到繼承的60秒來源冷卻，沒有呼叫即結束。V8.2在無進展且主機短冷卻剩餘不超過60秒時，以最多5秒短等待接續同批執行，避免多等10分鐘喚醒。冷卻時間不縮短，超過60秒的限流仍保存進度離開；測試確認不繞過主機限制。




## 雲端恢復驗收（台北2026-10-26 23:15）

恢復執行40347407061全部步驟成功；雲端732項測試通過；OAuth及原ROOT/REPORT資料夾唯讀驗證成功。五個指定workflow狀態均已驗證active。新批次：5=40347487591、5-1=40347497425、6=40347506553、6-1=40347516054，均已啟動。1/3/4保留run40340814860執行；2該批仍為舊504失敗。API拒絕在同一run仍執行時單獨重跑job，因此2等待後續既有定時批次，不能寫成目前八條皆成功下載。舊等待run40206907842已由恢復程序取消。官方排程cron實際為每小時第7分；TDCC/TAIFEX為每10分鐘，GitHub可能延遲。此次未更改頻率。尚無本次新增RAW及缺口補正總量驗收；來源未提供/未驗證資料保持開放。

恢復證據：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40347407061
