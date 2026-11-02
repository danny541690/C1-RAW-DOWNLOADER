# WP00 B64 SDK批次與錯誤回應稽核9/9（2026-10-14）

本機及GitHub同9案例9/9，完整JSON及兩hash一致，不算18新案例。4正常/明確拋錯控制，5限制成功重現；PASS不代表缺口已修復。

## 固定證據

FinMind/FinMind commit8b42547c1e34f77823dd8d3836c1fc1388bc5678，FinMind/data/finmind_api.py blobeb114b2e212862442a02dce6f4b824ab6f5fbd3b。
CRLF→LF原檔hash978b9678071d7dab151d268c3d6d885be2b0aa7559d2527283c0e25e718afff3，載入前核對。
scripts/experimental/wp00_b64_async_error_audit.py，code commit25fbcb614cba69c6d9da3f28ea327d8193e6d0f3，hash5f7d69624e6d3f74249b4d660319b629887a917311d3812921ac7a0c3eb85b53。
workflow commit32a9e6cf80e1432b7034b116e6e2dbbb12246c3e。
run https://github.com/danny541690/C1-JARVIS/actions/runs/38478178647 ，job115573980905 success。
artifact11857125667，下載ZIP SHA2560bd3397e172c72c4fa567575f7c85153bb91fef098f51c74e47925d342b10e3e，與GitHub digest一致。
結果docs/registry/delivery/wp00/b64_cloud_results_20261014.json。

## 測試方式

AST抽取原FinMindApi的get_data及async聚合/compatibility/extract/dispatcher方法，保留private name mangling，pandas2.2.3。async_request_get与request_get皆由fake替換。測的是SDK聚合函式，未啟動真實async executor、HTTP、重試或限流。fake Response.__bool__設定HTTP status<400為真，模擬falsey error input；沒有驗實際transport會返回哪些Response型別/列表長度。所有fake公司及營收只作控制，非市場樣本。

## 結果

| 案例 | 實際觀察 |
|---|---|
| 兩正常回應 | 合併2列 |
| data_id_list非空且use_async=False | 仍進async聚合路徑、建2請求參數 |
| 一正常＋falsey503 | falsey回應略過，只留1列且不拋錯 |
| 2請求只回1 response | 不核response count，只留1列 |
| 兩回應都是None | 回空DataFrame而不拋錯 |
| HTTP200 JSON status402且data=[] | extract不核status，只留另一成功列 |
| 同步data=null | pd.DataFrame(None)形成空表 |
| 同步明示data=[] | 正常空表控制 |
| truthy回應缺data | extract拋unexpected response |

5個LIMITATION項目分別為falsey略過、回應短缺、allNone、JSONstatus忽略、syncnull。這些是輸入條件下的真方法行为，不宣稱真實API已發生上述故障或通常返回某種null/error schema。

SDK的輸出DataFrame不能單獨作整批完成證據；空表不能證明來源明示0筆成功。缺少逐請求accounting時，一個成功公司不代表另個成功。provider transport若提供更強完整性保證須另查，本輪不以fake作其定案。

## 決策與接續

B64只新增稽核，未改FinMind程式、未整合Runtime。下一輪實驗adapter保留每個請求identity/status/缺件，整批只在每筆有效成功且identity符合時PASS；null與錯誤空表HOLD，明示成功空array另分類。先離線反例驗證，再有契約才考慮真實試抓。原unit/currency/date/PIT仍OPEN，不因accounting測試提升來源資格。

市場API0/帳戶0/protocol0。B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

