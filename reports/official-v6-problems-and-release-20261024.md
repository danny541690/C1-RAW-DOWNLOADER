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
