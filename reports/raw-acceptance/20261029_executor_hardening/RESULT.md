# I17／I18執行器修正與驗證

日期：2026-10-29（台北）；版本：20261029_R3。狀態：核心修正已完成，正式七來源整合仍未完成。

## I17 錯誤分類與恢復

- 來源逾時/暫時錯誤進RETRY_WAIT，保存錯誤階段、類別、嘗試與下一時點；429/503尊重Retry-After並由頭尾共用冷卻。
- 授權錯誤進SOURCE_HOLD，內容錯誤進CONTENT_BLOCKED，未獲下載授權進APPLICABILITY_HOLD。儲存/回讀錯誤保存RECONCILE，不當成新市場請求。
- 既有原件先保存預期SHA與參照，再讀取；回讀中斷仍可恢復。存檔已有save_intent者按確定locator/SHA恢復，不重送市場。
- 無save_intent的中斷要有adapter提供storage_checked、receipt_checked、NO_DURABLE_RESULT及evidence_id才可重試；計數不重設，已有4次者仍阻擋。正式adapter必須實作真實對帳，不能自行填true。
- 錯誤紀錄不寫入例外文字/URL/token/回應內容。網路故障、限流、授權、內容、存檔成功後回應丟失等本機故障注入均有測試。

## I18 舊收據SHA與身分綁定

重用必須取得expected_receipt，逐一核對來源、task_key、期間、原件參照及舊SHA；目前bytes不符舊SHA立即隔離，不能用目前bytes算出的新SHA覆蓋舊證據。缺契約或身分不符也不重抓、不放行。

## 實際驗證

116項本機測試、12preview YAML檢查通過。GitHub run40832464478 start與fresh-runner resume均success：使用真實Drive TWSE既有原件，正確舊SHA通過；刻意錯誤expected SHA進CONTENT_BLOCKED，跨執行環境仍存在且嘗試0。零市場請求、零RAW寫入。原生2014-08-29價格資料中的2348空值仍保留內容待查，不核准numeric/PIT或完整驗收。

雲端錯誤SHA案例只變更隔離QA收據，不變更任何原始資料。最後補充錯誤碼/phase持久化的細節以本機116項回歸驗證；不將故障注入或原件重用冒充真實缺件下載成功。

## 尚待事項

I12/I13：正式七來源adapter、舊查核任務轉正式狀態、真實缺件/解析補正→Drive新存檔→重驗及負載。實際workflow_dispatch與全量分頁先前已通過，但仍須接入正式入口。舊排程保持停止，新12條不啟動大量處理。I17/I18標記是核心範圍修正，並非整體部署核准。

