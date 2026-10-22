# 賈維斯 v0.93 第六排程：缺漏對帳與修復規劃

日期：2026-10-22（Asia/Taipei）。狀態：PLANNED_NOT_DEPLOYED。本次只保存規劃與來源證據，未建立或啟用第六條 Actions 工作流程，未修改現行五條的預算、鎖或斷點。

## 1. 建議配置與責任

- 名稱：RECONCILE_REPAIR，第六條缺漏對帳與修復協調。
- 建議每小時 :15 觸發，每次最多60分鐘；Actions逾時75分鐘，持久租約90分鐘。各階段借用未用完時間，不為湊滿時間空跑。
- 同排程一個執行者，獨立concurrency與持久鎖；六條可並行，但每個資料分區仍只有原負責stage可以寫入。
- 處理固定授權範圍2026-10實際可得資料至2000-01，月份由近到遠；已知阻塞交接的高優先缺口先處理，未解決項不得阻塞全部歷史掃描。
- 檢查原始檔、QA1帳本、三條轉換帳本、隔離記錄、RAW retry_months及既有來源能力清單。只寫第六條自己的缺失帳本、任務佇列與候選證據，不直接改寫第一至五條的權威帳本。

## 2. 目前程式必須補上的接點

目前已有各stage獨立租約，沒有跨stage共用的逐單元修復交易。process_units遇到已存在的output_key會跳過，隔離單元也不會自動重新執行；corrections是待修記錄，不是已運作的自動修復器。因此第六條不能只是新增cron。

實作必須加入三個交接點：RAW讀取定向補抓任務；QA1讀取指定RAW hash的重驗任務；PRICE/FINANCIAL/CHIP讀取有核准解析器版本的定向重算任務。每個owner只更新自己的stage輸出與收據。

新增全資料集預期清單，才能找出完全未落檔的缺口；只掃現有資料夾無法證明歷史資料完整。

## 3. 一輪工作流程

| 階段 | 工作 | 產物與責任 |
|---|---|---|
| 讀取與對帳 | 按來源、歷史上市櫃資格、資料集、有效日期建立預期單元，與已保存收據比對 | 第六條GAP_LEDGER；歷史母體無證據時標UNKNOWN，不臆測缺口 |
| 分類 | 區分缺檔、來源真的空值、解析失敗、儲存衝突、數值/單位矛盾、PIT缺證、來源不提供及等待上游 | 每個gap附證據、原因、owner與下一步 |
| 選修復方式 | 先重用現有RAW修解析器/映射；確實缺檔才安排下載；來源矛盾保持隔離 | REPAIR_TASKS，禁止把所有QUARANTINED當成漏抓 |
| 交回原排程 | 下載交RAW；重驗交QA1；價格/財報/籌碼重算交各owner | 各owner在自身鎖下執行；第六條不直接改權威輸出 |
| 回讀驗證 | 比對新檔hash、來源身分、股票/日期、欄位、單位、公告證據及下游收據 | 已送出或HTTP 200不等於修復完成 |
| 結案與報告 | 滿足該缺口驗收條件才RESOLVED；其餘保留明確待辦 | 不把基本QA/暫存當數值或PIT核准 |

時間建議：對帳15分鐘、分類與準備修復任務30分鐘、讀回結果10分鐘、保存報告5分鐘。等待owner時保存WAITING_OWNER後繼續其他任務，不長時間空等。

## 4. 缺口分類與處理

| 分類 | 第一處理方式 | 不可做的事 |
|---|---|---|
| RAW_MISSING/CORRUPT | 先對帳既有封存，再交RAW從原官方來源補抓；相容證據充分才換來源 | 有一個檔案就跳過整月，或直接覆寫RAW |
| PARSER_MAPPING | 使用原RAW修證券代碼/日期映射，核准新解析器後定向重算 | 只把錯誤改標PASS，或沒有測試就自行改解析器上正式線 |
| STORAGE_CONFLICT | 回讀bytes與hash，分開保留各版本，確認正確血緣 | 直接刪除衝突檔或強制覆蓋 |
| NUMERIC_UNIT_CONFLICT | 對照定義、股/張、元/仟元、單季/累季、原價/還原價及交易範圍 | 用不同口徑的資料拼成同欄，或以多數決認定正確 |
| PIT_OR_UNIVERSE_UNKNOWN | 尋找當時證券資格、首次公告與更正版本證據 | 用今日股票名單回推2000年，或把下載時間當首次公告 |
| WAITING_UPSTREAM | 由前序owner完成指定hash驗證後喚醒 | 重複下載同一個已保存成功單元 |
| SOURCE_UNAVAILABLE/NOT_PUBLISHED/NOT_APPLICABLE | 區分歷史不提供、尚未公布、休市、當時未上市等 | 一律補零，或把正常非適用當漏抓 |

## 5. 鎖、重試與重新處理

- 沿用同來源同單元「首次一次＋最多三次重試」與既有attempt ledger；新增第六條、重開機、切換批次均不重設次數。耗盡仍列RETRY_EXHAUSTED，不每天另開四次；是否重啟需新證據與明確政策。
- HTTP timeout/429/5xx採有界退避與來源熔斷；驗證錯誤不盲目重抓。未知中斷先對帳收據與bytes。
- RAW依現行max_capture_jobs=1繼續單一寫入者。第六條只交下載任務，不能再另起不受鎖保護的下載器。
- 上線時可在RAW原60分鐘內，初始預留最多6分鐘給已核准補抓任務、其餘54分鐘歷史；無補抓時全部回歷史。這是建議方案，尚未修改現行RAW程式。
- 新修復鍵至少包含logical_unit、input_hash、repair_kind、parser_version、rule_version。task以claim/ack防重複；同一輸入與版本只執行一次。
- 改解析器後只重算受影響白名單，不把所有R2暫存重新做一遍；新檔保存新版本，舊隔離證據與RAW保留。
- 原來源RAW與其他供應商下載檔分開保存；只在欄位定義、日期、證券身分、單位、頻率及可得時間相容時建立fulfilled_by，不把供應商加工結果偽稱官方原始回應。

## 6. 補資料來源清單與驗證程度

既有四來源TWSE/TPEx/MOPS/FinMind仍為主線；以下是新增候選，並非已接入正式下載器。

| 來源 | 正式介面、費用與歷史範圍 | 建議角色與限制 | 本次證據程度 |
|---|---|---|---|
| TDCC集保 | 官方OpenAPI及CSV，股權分散資料免費；歷史查詢頁標示保存期間一年，不代表API可任意回溯 | 優先加入股權分散、股務資料；不能替代全市場價格/財報或保證補2000年 | 規格JSON與/v1/opendata/1-5實際HTTP 200，69751列，資料日期20261016；需清除日期欄BOM |
| Fugle富果 | 正式HTTP API；免費基本方案歷史行情60次/分鐘；個股日資料自2010年、指數2015年、興櫃2024年；單次查詢小於一年 | 優先測日OHLCV缺口；免費不含盤後籌碼/股務事件，須API key；還原價、成交量與交易範圍須另證相容 | 官方文件已核對；未使用使用者金鑰實測 |
| FinLab | 官方Python data.get/data.search；免費台股歷史截至2023-12-31，欄位起點與權限逐表確認 | 可作早期價格、營收、財報候選補充；加工/修訂資料與原RAW分開，免費舊資料不等於免費PIT版本；as_of版本功能需要付費資料方案 | 官方文件已核對；未用使用者帳號實測 |
| 富邦新一代API | 正式SDK/行情HTTP API；歷史股價自2010年；TDCC整理資料自2013-07，2015-05-08前為月頻 | 有帳戶與對應權限時列第二階段；不能未驗權限就標免費；與Fugle可能同資料供應鏈，不視為獨立Golden | 正式文件已核對，帳戶/費用/資料權限尚未驗證 |
| TAIFEX期交所 | 官方OpenAPI/OAS，公開端點依資料集確認歷史及授權 | 補期貨、選擇權與市場風險指標；不替代台股個股價格或財報缺口 | 官方API入口已確認，端點/歷史樣本待實測 |
| TEJ | 正式API，需申請金鑰與產品權限，不能列為長期免費來源 | 免費來源證實無法補齊關鍵歷史資料時的付費備選；本次未購買或開通 | 正式文件已確認，未驗證帳戶與方案 |
| Goodinfo/玩股網 | 本次未查得可據以採用的正式免費API文件；玩股網另有資料使用授權限制 | 保留人工對照/待洽授權，不以網站私有XHR當已核准API | 不列入第一階段自動補抓 |

使用順序按資料類型路由，不是把所有來源逐個掃完：原官方來源→FinMind相容補洞→TDCC或Fugle或FinLab等已驗證相容來源→需帳戶/付費來源候選。TDCC本身是股權分散的原官方來源，優先於轉載站。

來源相依圖須記錄origin_provider；轉載同一官方檔案的三個平台不能當三份獨立正確性證據。Fugle/富邦共通欄位與供應鏈未釐清前不算獨立對照。

## 7. 儲存與進度表

建議在既有05_CONTROL下新增REPAIR_V1，內含SOURCE_CAPABILITIES、EXPECTED_UNITS、GAP_LEDGER、REPAIR_TASKS、CURSOR、STATUS與按年月保存的執行收據。主控資料只存專案既有私有Drive，公開repo不新增使用者資料夾ID、金鑰或大批原始資料。

缺口紀錄至少包括：gap_id、來源/市場/資料集、證券及歷史身分、資料期間、reason、evidence_hash、owner、attempts、next_retry_at、parser/rule版本、來源費用/權限、最後結果、修復輸出hash、QA及下游收據。

狀態：OPEN→CLASSIFIED→WAITING_OWNER→REPAIRED_PENDING_QA→RESOLVED，或WAITING_EVIDENCE/RETRY_EXHAUSTED/SOURCE_UNAVAILABLE。基本缺檔已修復可單獨結案，但NUMERIC/PIT缺口必須有各自證據才結案。

每批報告：預期單元數、實存且基本驗證數、確認缺漏數、格式隔離數、數值/PIT待證數、來源不提供數、當批新增缺口/修復/待驗數、請求與bytes、運作分鐘與每分鐘完成單元、最舊掃描月與最後成功修復期間。覆蓋率按資料集/歷史母體計算，不以掃過月份比例代表資料正確率。

## 8. 上線前驗收與階段

第一階段先讀取現有待修帳本與預期清單，做可重現對帳，不下載新來源。以價格線2026-10既有隔離（16單元：14證券代碼映射、2日期辨識）作第一個解析修復案例，保留原RAW。

第二階段逐來源小樣本：TDCC最新一期及區間邊界；Fugle上市/上櫃/已下市、休市、除權息及2010邊界；FinLab免費截止前後、欄位權限、原價/還原價及歷史身分。確認授權/帳號/limits/費用、實際可下載範圍、hash與定義後才開啟來源。

第三階段整合owner任務接收、白名單重算與hash交接，驗證六條同時執行不重複寫入；測試中斷/重送/409/429、嘗試次數不歸零、隔離不當成功、任務已送出但未處理不結案、晚到資料重新對帳。

驗收後才新增正式第六條workflow。現在沒有完整的第六條執行器，不能把本計畫或來源文件查證稱為已上線修復。

## 9. 官方參考文件

- TDCC API：https://openapi.tdcc.com.tw/ ，規格：https://openapi.tdcc.com.tw/tdcc-opendata-api-docs
- 股權分散免費及授權：https://data.gov.tw/dataset/11452
- TDCC歷史查詢：https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
- Fugle方案：https://developer.fugle.tw/docs/pricing/
- Fugle日K：https://developer.fugle.tw/docs/data/http-api/historical/candles/
- FinLab下載：https://finlab.finance/docs/details/get_data/
- FinLab API/PIT版本權限：https://finlab.finance/docs/reference/data/
- 富邦股價：https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/historical/candles/
- 富邦股權分散：https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/ownership/tdcc-distribution/
- TAIFEX：https://openapi.taifex.com.tw/
- TEJ：https://www.tejwin.com/en/insights/tej-api-document/
- 玩股網條款：https://www.wantgoo.com/terms-and-policies

文件核對日2026-10-22；除TDCC公開端點外，其餘新增來源尚未用使用者帳號/金鑰完成下載驗收。沒有承諾2000–2026年全欄位可免費補齊。
