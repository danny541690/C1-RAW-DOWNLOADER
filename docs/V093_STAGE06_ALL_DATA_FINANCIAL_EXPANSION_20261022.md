# 賈維斯 0.93：全資料缺口範圍、財報修復與中斷續跑

更新：2026-10-22，台北時間14:32快照；後續數量以正式月分片為準。

使用者已授權六條持續運作，第六條終極目標為所有資料庫原始資料與衍生修復對帳完成，含財報；不需再次確認上線。原始檔、下載次數、隔離證據與主要斷點保留。

## 已部署及實證

- 新增 MOPS_MATRIX_FINANCIAL_REPAIR_V1，支援損益表、資產負債表、現金流量表。MOPS 比較矩陣的科目標頭與公司數值分表，原通用 R4 無法正確處理；新版本核對報表、公司欄序、期間、範圍、金額單位及每個原生座標。
- 14份既有原始財報／13,276數值格的隔離實測通過，原檔雜湊與不可覆寫輸出已核對；市場HTTP重抓0。三種報表皆有真實樣本。驗證證據SHA256：292e519157bf794f5abdf086b96df52db181bec519c11ffe9e169018d715cb06。
- 正式財報修復run39732814594已運作：2023-03這批89個缺口，89個缺口全數RESOLVED、89新版任務DONE，舊89任務CANCELLED_SUPERSEDED；首批86項成功，尾批39734375138成功3項，兩批失敗0。原89個舊版BLOCKED任務會在新版結案後標示CANCELLED_SUPERSEDED，不能把兩個版本相加成缺口數。
- 已獨立從Drive讀回一份正式現金流修復Parquet及驗證JSON，與公開正式收據SHA256一致。978個有數值的原生格，另1222個原生缺值保留缺值。輸出17896bytes、SHA256 24eb638067d532b703c78ecd5666cffd9605eb28aae094a5716f7026ae4e4d11；驗證1593bytes、SHA256 15d8a7b5ebe55a175d7433a5cb121921b9e4a7292d049564b75fb10bf17065cf。
- 財報保留來源原生金額單位、累計YTD與資產負債時點INSTANT，不自行轉當季或猜公告時間。新輸出仍STAGING_ONLY；逐格重現不等於數值語意、PIT、全市場完整性核准。
- 本機及雲端450項回歸通過，雲端run39732814600；該run的真實Drive canary在push時刻意略過，不能稱其新增真實Drive測試通過。先前實際Drive／fence驗證仍保留。

## 重新接續的工作

先前RAW／QA1／CHIP／第六條工作於約台北13:58遇GitHub HTTP403失敗，後續PRICE與FINANCIAL啟動也曾失敗。歷史錯誤沒有額度回應標頭，根因未確定，不能直接宣稱額度耗盡。2026-10-22T06:22:20Z新probe顯示limit5000、remaining4865。

已加入403/429診斷（只記安全的狀態與額度標頭）、啟動前預算檢查、空月稀疏checkpoint、每次發布仍新讀GitHub HEAD並以CAS核對owner/fence、快取讀取不允許舊owner發布。原工作查鎖由20秒改120秒，90分鐘租約保持。

四個舊owner皆先由GitHub確認run已completed/failure，才清除其精確持久租約；保留last_fence及全部收據。未清除當時仍在執行的FINANCIAL租約。常態五線各60分鐘；一次性財報 backlog 執行15分鐘，之後常態FINANCIAL每輪先在自身60分鐘內使用最多6分鐘消費修復工作。

- 恢復RAW／QA1／PRICE／CHIP：run39733481658，四個job皆實際進入worker步驟。
- 恢復第六條：run39733481451，成功從保存的掃描位置接續，33個月後到2000-01；控制帳本month_index322、next_month=null。
- 下一個常態第六條會開始新一輪由新到舊掃描，持續收納其他排程新交付的RAW與缺口；缺口／任務去重，已修復收據保留，不覆寫RAW。
- 原RAW仍從2014-04之後已推進的真實斷點往2000-01；不能重設回2014-04。下游從已保存進度接續。

程式提交：31d8558a96d7e4e2fe4801faa607a78253e4d2ad（財報與全資料缺口）；753abe63cb755fb273b7bc353c0b12bea1277d58（API讀寫與診斷）；6e29433a914cb896bc58fdf03d44b3cbdd59de3b（恢復與常態預算閘）。私有鏡像344d93dd37625ab2bb53d372ffc4bd9de04767be。

## 全資料目標與仍缺工作

資料集登錄包括價格／指數／交易資料、公司行動、三大財報、月營收、法人／融資券／持股分散／分點、歷史證券主檔、交易日與PIT。四既有來源的已記錄RAW失敗也匯入缺口，成功單元不重抓、原次數不重設。

目前正式自動修復器為PRICE原生指數／公司行動與FINANCIAL三大財報。其他資料類型持續列BLOCKED_APPROVAL／證據HOLD，尚不能稱全部類型都能修。RAW額外補抓的正式transport／原持久次數綁定尚未啟用；完整預期單元名錄、歷史母體與可得性證據仍不齊。未索引月份是UNKNOWN，並非沒有缺漏。all_data_repaired=false，production_data_approved=false。

## 額外來源查證

- FinLab：先將使用者「Finland」理解為FinLab；官方文件有data.get、財報／營收資料與認證方式。免費台股歷史截至2023-12-31，不能當2026免費補洞保證。尚未確認使用者授權與各資料集權限，未啟用抓取。
- TDCC：官方OpenAPI可用於集保持股分散；需完成歷史可得範圍、欄位與口徑驗證後接adapter，未啟用。
- Fugle：有官方API，需確認認證與方案範圍，未啟用。
- Goodinfo：官方網站可查詢，但尚未查證到可直接採用的正式公開大量下載API；不能視為已取得穩定免費API。TAIFEX依資料集另做範圍核對。

官方參考：
https://finlab.finance/docs/details/get_data/
https://finlab.finance/docs/reference/data/
https://openapi.tdcc.com.tw/tdcc-opendata-api-docs
https://developer.fugle.tw/docs/data/intro/
https://goodinfo.tw/tw/
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

## 對話中斷判讀與下一接點

聊天顯示中斷可能來自連線、工具逾時、服務限制或對話長度；無該次事件紀錄不能確定原因。GitHub Actions獨立於聊天，應查run終態、lease、cursor與原生收據；對話中斷不等於雲端停止。重啟先對帳未知結果，不能盲目重送或重設計次。

下次先查39732814594、39733481658與正式財報2023-03月分片；確認這批89項已完成及所有者租約釋放，再接其他月份。掃描完成與財報這批完成均不代表全資料庫已補齊。繼續實作RAW真實補抓綁定、其他類型processor與完整預期單元證據，新增來源須先驗證口徑／權限。

尾批提交b73e94574d5af28eb3199db5fda3a8fdb1c5491c、run39734375138成功；首批86＋尾批3＝89項，這批無未完成缺口。其他月份／其他資料類型仍待持續修復。
