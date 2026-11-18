# JARVIS v0.97 R3｜143項 G2 官方格式候選正式核證結果（2026-11-18）

## 真實執行

GitHub:
- 143項共用契約首次核證 Run: https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44244550130 SUCCESS
- 七來源缺證分組與二次核證 Run: https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/44244777422 SUCCESS

核證結果：正式已批准共用契約 **0/143**；正式逐筆 G2 已發 **0/74,750**。這些是缺少權威原生規格認證及版次證據的 HOLD，不是已驗證損毀的檔案。Google Drive 隔離證據：`03_DATA_QUALITY/R3_G2_TEMPLATE_APPROVAL_ISOLATED/r3_g2_143_template_review_run_44244777422.json`，已獨立讀回。

## 分來源143項共用候選資料集的缺證表

|來源|候選契約|未能證明官方資料集/版次|缺必要欄位規格|缺原生主鍵規格|正式批准|
|---|---:|---:|---:|---:|---:|
|TWSE|32|32|28|20|0|
|TPEx|35|35|30|20|0|
|MOPS|24|24|20|8|0|
|TDCC|6|6|4|2|0|
|TAIFEX|12|12|10|8|0|
|NDC|30|30|24|12|0|
|FinMind|4|4|3|2|0|
|**合計**|**143**|**143**|**119**|**72**|**0**|

缺證分類彼此重疊，不能加總當作不同格式的總數。

## 本次已完成

1. 讀取 repo 143項候選，去重並核對七來源格式期間與 Dataset 身分。
2. 逐項檢查必要欄位、主鍵、來源-時代與日級生效版次官方證據；產生七來源優先補證清單。
3. 檢查正式核准登錄簿 `R3_G2_APPROVED_TEMPLATE_REGISTRY_V1.json`：查無核准登錄（不是假設有 PASS）；隔離審核以 `official_document_drive_id` 原始文件 bytes/ SHA、官方 domain、獨立審核記錄、期間與欄位為核准依據。單純一個布林 true 不足以核准。
4. 對七來源凍結 74,750 筆母體逐來源確認精確筆數；但沒有以候選格式直接發證，也沒有修改原始 Bronze。
5. 發布不可變 G2 候選審核報告至獨立 Google Drive QA folder，完整讀回成功。

## 仍需做的實質認證（不能用成功測試充數）

- 逐 (source,dataset,edition,day-level effective window,native layout) 取得官方原始格式規格文件和官方出處；將來源頁、實際文檔 bytes SHA、發布/生效時間及確切欄位/主鍵證明存入 Drive。
- 因部分歷史格式原始官方文件未能直接取得，必須依歷史原始下載保留證據和已驗證舊版公告再比對。缺乏獨立來源證據的格式維持 HOLD；不可編造 `official_attested=true`。
- 將有證據的 approved 共享模板與每個 source_id 的 dataset/date/native signature/source SHA 綁定，保存 G2 逐筆不可變憑證和遠端 SHA 讀回。未完成上述條件前不擴張正式逐筆認證。

## 核心邊界

GitHub Run SUCCESS 表示審核稽核程式成功、報告落地，不代表143項批准。正式 R3 Master 未發布、R1/V3 不變、Bronze只讀、Silver/Gold不轉換。
