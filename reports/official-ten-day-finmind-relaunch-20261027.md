# 三官方＋FinMind 補缺：近十天問題查核與重新上線（2026-10-27）

## 查核範圍與可證明程度
使用者要求2000-01-01至2026-10最新原始資料補正。本次以2026-10-17 00:00 UTC至10/26 22:45 UTC取得紀錄作擴大追溯（不是把UTC窗口冒充精確十個台灣曆日）。
全庫取得1,864筆工作執行清單；篩選8個相關下載／補正／FinMind歷代工作流程269筆，其中29次執行結論失敗，35個失敗job日誌全部讀取。成功執行不代表單元成功，本次另檢查現行四條STATUS／問題摘要及原始程式。沒有逐一讀完269次所有成功job的每一行，也不能重建未保存的歷史訊息；因此下表是可追溯的已知問題全集與處理狀態，不能聲稱已發現每一個未記錄的錯誤。
機器清單：[official-ten-day-run-index-20261027.json](official-ten-day-run-index-20261027.json)。測試故意注入的錯誤不算真實來源故障。

## 重新上線
正式執行：[40415482911](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40415482911)。
來源版本：3ecfcfb791df9c4b0d2c567784e0f83b11731064。756項本地測試通過；GitHub checks通過，四條均進入查核補正步驟。
排程1 RECENT_ASC：2013-01→2026-10；排程2 RECENT_DESC：2026-10→2013-01；排程3 EARLY_ASC：2000-01→2012-12；排程4 EARLY_DESC：2012-12→2000-01。
保留原RAW、月鎖、各方向斷點；已走過月份進入缺失／FinMind補缺重訪佇列；不把重訪等同全月正確。

## 問題、根因與處理
|編號|已知問題／證據|根因與影響|處理與仍開放事項|
|---|---|---|---|
|01|FinMind停用：線上原程式finmind_enabled=False、禁止非官方來源|官方失敗後沒有替代補下載|本次啟用獨立FinMind補缺模組及兩種既有token secret別名；不更動官方來源限制本身|
|02|FinMind舊版NameError start未定義；run39232220305|舊單一年度批次未開始有效下載|不重啟該舊程式，改用有日期邊界與讀回測試的新模組|
|03|Google invalid_grant；runs40197934581、40202190813，共8個失敗job|refresh token過期或撤銷，四條同停|使用者已改production並更新配對憑證；後續成功Drive寫入證明已越過該阻礙，不保證永久授權|
|04|Drive 403 userRateLimitExceeded；run40129604648|共享Drive讀寫限流|已對明確限流原因有限退避；一般權限403仍停，不盲目重試|
|05|GitHub 403；12個所選失敗run含該錯誤|控制API／交接無法繼續；不能一概歸因官方網站|保留共享預算與鎖；讀取先等額度，權限拒絕不能用無限重試掩蓋|
|06|GITHUB_BUDGET_WAIT_LIMIT_REACHED_NO_LOCK_ACQUIRED；runs39880182189、39864465853|額度不足，未取得鎖便停止|保留有界預算等待；下次喚醒續接，不冒充資料已下載|
|07|HTTP504；run40340814860|GitHub控制讀取暫時失敗|已部署GET有限重試；非冪等修改不盲目重播|
|08|HTTP404；run40350890117在月鎖commit的控制manifest讀取發生|不是官方資料404，控制檔／權限／路由仍需區分|保持失敗可見；不把控制404當歷史無資料。其後批次已恢復，原次失敗不能刪除|
|09|DNS解析失敗、TimeoutError／URLError|官方傳輸無回應，常見2014-03、2013-07、2012-06/08/09/12|保存請求意圖，有限次數＋冷卻；跳過故障單元繼續其他單元|
|10|IncompleteRead／chunk解析invalid literal int base16 b''；run40116000096|HTTP本文中斷，不可把截斷資料存成正確|既有Drive層已加不完整讀取重試；最終仍需完整讀回與SHA核對|
|11|existing remote file SHA mismatch；runs39856967673、39848259193、39840151896|既有遠端與預期位元不一致|保留舊檔與失敗證據；內容定址存新版本、讀回核對後才更新收據。不能直接覆寫消除異常|
|12|MONTH_PLAN_CONFLICT、ambiguous source folder；run39457643971|舊月份計畫／重複資料夾身份不一致|使用現行分區與FolderRegistry；不重新啟用舊版錯誤路徑，歧義資料夾不猜選|
|13|新補正中間版本NameError os未定義；runs40413171608、40413174928|測試gate擋下，並非官方來源錯誤|已修正初始化；完整回歸通過再交接。這兩次不能算資料補正成功|
|14|SOURCE_NO_DATA_UNCONFIRMED、EMPTY_RESPONSE_NOT_COVERAGE|可能假日、未上市、參數不合或歷史不提供，空白不證明無資料|保留未知缺口；有對應資料集及歷史代碼證據才進FinMind；回傳仍空白就維持未完成|
|15|OFFICIAL_PERIOD_NOT_PROVIDED|官方明確最低日期限制，早期2000年代突出|保留來源界限；FinMind可供者另存補充，不能宣稱官方歷史原件取得|
|16|OFFICIAL_ROUTE_NOT_FOUND／UNRESOLVED_OFFICIAL_ROUTE|網址／歷史路由不可用|保留原回應、已確認官方路由；FinMind僅對已映射資料補缺，無映射仍列出|
|17|FINANCIAL_REQUESTED_COMPANIES_OR_PERIOD_INCOMPLETE／selector rejected|MOPS請求公司、季度或端點範圍不完整|僅規劃明確缺失公司／報表／季度，保留codes_found；FinMind逐檔補缺，不以一家公司代表全市場|
|18|LOCAL_PARAM_ENCODING_ERROR／重複companyId鍵|表單參數結構錯誤會讓財報無效|保留既有重複鍵編碼修正與回歸；參數先驗證，失敗不發出無效請求|
|19|已檢查卻0補正、LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS|部分是解析、欄位規則或PIT待驗證，不是RAW壞檔|兩類分流：缺失才重抓；有效RAW解析問題走保留證據／重解析；不為提高下載數覆寫正確檔|
|20|NUMERIC_FIELD_RULES_NOT_COVERED、MISSING_NUMERIC_CELL|未知數值欄位／缺值沒有通過完整數值驗收|持續列未驗證；本次不把有檔、JSON有效或SHA一致當全面數值正確|
|21|OHLC關係／NO_VALID_TRADE_PRICE_REQUIRES_REVIEW|有時停牌無成交，有時缺值；不能憑空補OHLC|現行官方欄位檢查保留；新增FinMind OHLC有限值、上下界、代碼及日期驗證；不填0、不修造價格|
|22|財報單位、單季／累計、會計恆等式、公告可得時間不明|FinMind與MOPS原生口徑可能不同；EPS受股數基準影響|原生來源分開保存，numeric_verified/pit_verified仍false；不跨來源直接合併或冒充PIT通過|
|23|歷史全市場公司清單尚未證明|目前代碼集合不能證明2000～2026每個日期上市櫃普通股全集|只用已保存官方該月代碼／明確財報請求代碼補抓；沒有名單則blocked列報，不拿今天全市場代替歷史|
|24|已走完月份被誤讀成全庫完整|月游標、run success與資料覆蓋不同|報告分請求／收到回應／讀回成功／未解缺口；coverage_certified維持false|
|25|重試上限後終止、已訪月不再核對新缺口|舊terminal與佇列會阻止再次補正|本次前一輪已開新授權的有界重試；本輪新增FinMind補缺月佇列，保留失敗歷史，不每次喚醒重設上限|
|26|FinMind額度／驗證／付費資料限制|即使程式接上，也不代表每一資料集、每一歷史日期免費可得|四條共享CAS預算200次/小時、至少18秒間隔；401/402/403/429共用1小時暫停；無token也可嘗試免費範圍，付費拒絕不循環硬抓|
|27|FinMind補充被當成官方缺口關閉的風險|第三方RAW不是官方原始檔，單月返回部分日期也非全部補齊|每筆連結official_gaps、covered_dates、unfilled_dates；source=FinMind獨立樹；official_gap_closed=false；成功需雲端讀回SHA一致|

## 最新已知缺口實例（不是全庫總數）
10/27 06:39台灣時間記錄：
- 排程1的2017-01月：來源空白7、品質待驗證165、共享節流等待8。
- 排程2回查2026-06：來源空白50、品質待驗證425、重試耗盡15、來源冷卻80。
- 排程3的2002-09：官方期間未提供127、來源空白172、內容不完整36、路由未解4、來源冷卻31。
- 排程4的2010-08：來源空白16、品質待驗證88。
這些是當時各月journal計數，不能加成全庫唯一缺口，也不能和後續同月狀態混合。
取消前最後舊批次STATUS顯示排程2已有2筆官方補正讀回成功；不能繼續說官方一直完全零成果，但其餘品質缺口仍大量存在。

## 本次執行方案與驗收
1. 先保留並讀取官方原件；僅明確官方失敗／缺公司項目進FinMind，解析品質標記不直接觸發盲目重抓。
2. 每次進入月份先做有限FinMind補缺，避免官方大佇列使其永遠無法執行；官方主流程持續。
3. FinMind成功獨立存原始JSON封包，股票代碼／日期／營收月份／財報季度核對；價格額外做OHLC關係檢查；寫入與雲端讀回核對SHA。
4. 共用限額與保留請求意圖；每單元最多3次，失敗／空白冷卻續跑。成功收據不重新下載。來源拒絕時保存原因與全域hold。
5. FinMind待補工作回寫月佇列，四條對向鎖及終止owner回收維持。沒有替代映射或歷史名單的項目列blocked。
6. 最終「全庫完整正確」必須另有每來源／資料集／日期／歷史證券全集、預期筆數、缺口、字段規則、重複／單位／公告時點的證據。本次重新上線不等於已達此標準，未聲稱所有解析與數值問題已解決。

## 主要程式與驗證
scripts/v093_official_finmind_gapfill.py；scripts/v093_official_repair.py；tests/test_official_finmind_gapfill.py；.github/workflows/v093-official-four-lane-repair.yml。
新增12項測試涵蓋明確缺口、成功不重抓、衍生品質不盲抓、未來日期、未知歷史名單、同月缺失日期合併、封包日期與股票驗證、OHLC、空白與額度拒絕、財報缺公司、共享CAS限額、存檔讀回與斷點重跑。

## FinMind原廠參考
- https://finmind.github.io/quickstart/
- https://finmind.github.io/tutor/TaiwanMarket/DataList/
- https://finmind.github.io/tutor/TaiwanMarket/Fundamental/
原廠資料集可用性及額度仍以實際回應為準；不把第三方補件誤標官方原件。

## 線上首筆請求查核與追加修正（10/27 06:58前後）
新版FinMind初次已真正發出請求：2014-06、1101、TaiwanStockPrice；FinMind回傳封包未包含該單元期望的2014-06-02，因此標記FINMIND_NO_REQUESTED_GAP_DATE，沒有冒充補齊。既有官方價格收據證實的日期從06-03等交易日開始；對06-02並無官方交易日證明。
追加：日資料只對已存在官方價格交易日證據的明確缺口發起逐檔請求；未知交易日保留blocked，不把空白直接改為不存在。blocked去重，避免大量重複訊息。
追加：長月份每45秒檢查一次FinMind待補工作（共享預算仍至少18秒一筆、總上限200/小時、每批每條最多40次），避免整批僅在進月時請求一次。這是輪詢間隔，不是承諾每45秒必有有效來源回應。
本機757項回歸通過；更新來源commit a7e53e1aef846bda91788d6bc2bc9f096d72ef89。
最新正式執行：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40416094064 ；雲端測試步驟已通過，後續以這個run核對實際請求與存檔成果。

## 最新正式批次實績（2026-10-27 06:57～06:58台灣時間）
run40416094064的checks已完成：757 tests OK，四條job都在RAW查核補正步驟。Drive STATUS四條均為新run且finmind_enabled=true：
- 排程1回查2014-06；排程2回查2025-10；排程3回查2002-02；排程4回查2012-11。這是重訪月份，不是整段全數已補齊。
- 排程4已實際FinMind請求1次、RAW存檔並雲端讀回成功1單元。資料集TaiwanStockInstitutionalInvestorsBuySell，股票1256，查詢2012-11-01至2012-11-30。
- 收據covered_dates為2012-11-14、19、20、21；仍有14個期望缺失日期未被該次回應覆蓋。單元狀態只代表來源封包已保存與基本驗證，不代表全月補齊。其餘資料仍待官方／替代來源或歷史市場身份核實。
- SHA256：710afbbb86c205602acbd25dfe8e13eadb3f35c531a88d2b9a1df27b01e8e37d；remote_readback_hash_verified=true；official_gap_closed=false。
- 該月FinMind計畫1260個查詢單元，已存1、查詢待處理1259，另16個缺口因未映射／交易日或名單證據不足列blocked。這不是全市場完整率，已存部分回應的unfilled_dates仍是資料缺口。
