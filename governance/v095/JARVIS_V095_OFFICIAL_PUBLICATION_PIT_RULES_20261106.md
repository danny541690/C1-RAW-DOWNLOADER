# JARVIS v0.95 官方資料可得性與 PIT 發布規則 (2026-11-06)

## 原則
1. 資料「屬期」不等於「公告日」；公告日不等於「抓取日」，最終 historical PIT 以可舉證的 `first_published_at`／更正公告時間為準。
2. 完整性分母必須依資料集、上市上櫃母體、交易日／每週日期、官網發布時點建立；無法以「六來源 × 三月份有檔案」的比例代表 98% 完整率。
3. `NOT_YET_DUE`、`NO_TRADING_SESSION`、`SOURCE_NOT_APPLICABLE` 不得列為逾期下載缺漏；`PARTIALLY_PUBLISHED_POSSIBLE` 需要蒐集早期已公告公司、不得假定全市場到齊；`DUE_CHECK_OFFICIAL` 需查官方實際申報是否完成，再列缺失。
4. 資料檔來源優先：v0.93 驗證原件、六大官方來源、其他政府官方機構或上市櫃公司原始公告、相容且可合法使用的 FinMind；Goodinfo、Yahoo 財經僅供線索與交叉核對，若未評估授權、使用條款與官方可追溯來源，不做程式大量擷取或直接作 canonical Bronze。
5. 14 槽並行不變；各槽只寫 run+lane 專屬不可變報告，不共同更新 Checkpoint；已驗證檔不重抓；公式、資料完整性與歷史 PIT 需獨立核准。

## 已核實之各資料規則
| 資料集 | 頻率與官網規則 | 2026-11-06 的狀態 |
|---|---|---|
| MOPS 月營收 | 普通上市櫃公司原則次月10日前；2026年部分保險及具保險子公司特殊適用者可延至15日前；須逐公司查正式申報日，非全市場同一天公告 | 9月應檢查所有適用公司；10月正在陸續公告，11月未進入申報期 |
| TWSE／TPEx 成交行情 | 每交易日盤後；櫃買特定商品版本有不同盤後產製時間 | 已完成且資料發布的11月交易日應檢查，不能一律視為未到期 |
| TDCC 股權分散 | 每週最後營業日持股快照，實際對外發布時點需另查 | 10月已發行週次應查；11月逐週核對公告與假日 |
| TAIFEX 期貨與法人 | 交易日盤後，依日盤／夜盤、商品及公告種類不同 | 11月已公布交易日應查，不可以整月資料夾空白判作合理 |
| NDC 景氣信號 | 按官方預告日發布 | 2026/09 於10/29 16:00公布；2026/10 預計11/27 16:00公布；2026/11 尚未到發布期 |
| 財政部關務署 進出口統計 | 依每期官方預告 | 2026/10初步值預計11/10 10:00前發布，11/6不應記缺件 |
| 經濟部 工業生產 | 依每期新聞稿公布 | 2026/09 已於10/23 16:00公布，10月以官方日曆確認 |

## 在六大來源之外需要補查的官方網站
- 財政部關務署進出口統計：<https://portal.sw.nat.gov.tw/APGA/GA30>
- 經濟部工業生產統計：<https://mnscdn.moea.gov.tw/MNS/Populace/news/News.aspx?kind=1&menu_id=40&news_id=124351>
- 政府資料開放平臺及 TWSE／TPEx 官方 OpenAPI；須注意部分政府頁面的更新頻率指整批資料／索引，不一定等同每公司公告即時更新。
- 個別公司 IR 官網可以確認公司發布時間，但同時保留 MOPS 法定申報與日後更正紀錄。

## 官方參考證據 URL
- 月營收次月10日前：https://twse-regulation.twse.com.tw/TW/law/DAT06.aspx?FLCODE=FL007250&FLDATE=20250930&LSER=001
- 保險業例外15日前：https://law.fsc.gov.tw/LawContent.aspx?id=GL000593
- 公開資訊觀測站：https://mops.twse.com.tw/
- TWSE 盤後：https://www.twse.com.tw/zh/trading/historical/mi-index.html
- TPEx 盤後：https://data.gov.tw/dataset/11371
- TDCC 週資料：https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
- TAIFEX 法人：https://www.taifex.com.tw/cht/3/totalTableDate
- NDC 115年9月及次期日期：https://www.ndc.gov.tw/nc_332_40618
- 關務署10月發布時點：https://portal.sw.nat.gov.tw/APGA/GA30
- 經濟部9月工業生產：https://mnscdn.moea.gov.tw/MNS/Populace/news/News.aspx?kind=1&menu_id=40&news_id=124351

## 持續驗收
各版本初次核對：`python scripts/v095_publication_gate.py`。其後由十四槽每輪對 Bronze 月份寫入 `official_availability_policy` 判斷。該判斷僅能幫助派工，不能單靠排程推定資料已發布，也不能擅自自動下載 Goodinfo/Yahoo。完整率、修正率、PIT、443 formula certificate 仍分別保留阻擋。
