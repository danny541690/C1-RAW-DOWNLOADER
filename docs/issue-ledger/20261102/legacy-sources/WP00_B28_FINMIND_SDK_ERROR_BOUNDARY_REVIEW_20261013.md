# WP00 B28 官方SDK錯誤與批次完整性邊界

僅閱讀FinMind官方程式並用假Session离線重現request_get，未import或執行整個SDK，無sleep實際等待，市場/帳戶API0。五個案例5/5重現既定程式行為，不是供應商驗收、不是市場資料正確5/5；B115934/934與38候選閘門維持，Production BLOCKED。

## 風險與證據

SDK request_get最後if response檢查依赖requests.Response truthiness；HTTP>=400为False。離線模擬200/402/403/504/傳輸全失敗：分別回200/402/403/504/None，504及傳輸錯誤到指定3次後返回，402/403未重試。這證明呼叫端不能只靠helper會raise的假設，仍要明查HTTPstatus。此處mock模仿Response布林規則，不是實際伺服器回應。

非同步工具catch每任務例外、verbose才log，回傳生存task列表；下游只取truthy response。此靜態程式路徑有部分結果無全批次request accounting的風險，未跑實際async測試、不宣稱已發生市場資料遺失。_extract_data僅檢data存在，沒在該函數核定應用status及列型別。

constructor有token才設Bearer；login_by_token會呼叫user_info，這批未執行。api_usage/limit字段缺失default0，不能當已驗證零配額。translation comment v4不支援與OAS宣告不同；依然缺實際契約證據。空日期參數送出不證明server合法或相同語意。

## 後續轉接規則草稿

HTTP狀態與JSON應用狀態分開核對；保存每個股票/日期請求結果，部分批次HOLD，不用DataFrame非空代表全數完整。缺列不當零/下市，明確錯誤不假裝無資料；權限/配額不循環重試、transient有限且用盡明確fail。擷取原始bytes與各請求血緣要在DataFrame轉換前。此批只文件/離線案例，未改既有runtime或官方SDK。

- docs/registry/delivery/wp00/finmind_sdk_error_boundary_draft_20261013.json
- docs/registry/delivery/wp00/finmind_sdk_offline_error_reproduction_20261013.json
- finmind_api.py官方blob：eb114b2e212862442a02dce6f4b824ab6f5fbd3b
- request.py官方blob：9e751b40052260683e179006f5ddfe6f42f95828

來源：https://github.com/FinMind/FinMind/blob/master/FinMind/data/finmind_api.py 、https://github.com/FinMind/FinMind/blob/master/FinMind/utility/request.py 。保留版本識別及選定結論，未repo複製完整SDK。

下一步將每請求狀態/完整性條件併入後續接口契約；精確日期/單位文件仍待確認，文件未通過不測市場樣本。興櫃RAW_ONLY。

