# 來源adapter、共用配額與隔離回應全批重驗（20261029 R10）

斷點已接續並完成本批。七來源遠端配額競爭7／7通過；期交所隔離回應兩分區重驗2／2通過，且各自自動Git／Drive保存與SHA讀回成功。本機144項回歸通過、12份受控候選入口設定通過。正式12條仍未啟動。

| 本批隔離檔進度 | 數量／意義 |
|---|---|
| 已檢查任務 | 1602個不重複任務 |
| 已檢查回應版本 | 1606份（同任務可能多版本） |
| 不重複回應SHA | 16種；兩分區合計實際讀取Drive RAW 30次，透過SHA快取避免逐任務重讀 |
| 舊SHA／版本完整性 | 全數通過；重試次數全部原樣保留 |
| 官方當次空回覆 | 1606份 |
| 可直接補正的有效CSV | 0 |
| 本批檢出檔案損壞／缺參照／儲存錯誤 | 0 |
| 已修復正式資料 | 0 |
| 已確認歷史不存在的例外 | 0 |
| 尚待來源範圍／其他官方檔案查核 | 1602個任務 |
| 來源重新下載／正式RAW寫入 | 0／0 |

「官方當次空回覆」僅證明保存的那次查詢沒有返回資料，不能認定該月份歷史資料不存在，也不能把空值改成0。原始隔離檔未覆寫或刪除；不把這批全部算成錯誤CSV或可直接重抓的缺件。

批次40875609531，程式125c64e55b74f34b490e22ad4b667035865b3176：分區0檢查798、分區1檢查808，每25份存一次Git斷點，兩區done=true。最後另由獨立連線讀回Git頁面，核對1606回應／1602任務／16 SHA與attempts不變。完整逐筆紀錄在jarvis-source-preflight/recheck-40875609531-1/TAIFEX，以及兩份自動Drive驗收封存（file_id 14iZU37mWJwAExZtEJNr3rwBse8Hp9KME、1Ys4HnwhOj7USo005TzxK0aSaUiVdE1d8）。本地quarantine-recheck-results.json保存收據與彙總。

前置工作與修正：

1. 新增v093_source_adapters逐任務factory，已接run_native_batch。舊RAW強制對照source/key/period/reference/舊SHA與legacy provenance；缺件須有來源證據、無可重用成功檔、無未對帳中斷；FinMind還需官方來源與定義、期間、頻率、單位相容核准。
2. 新增v093_source_rate：來源共享原子HTTP intent配額，頭尾方向不能各拿一份額度；限額拒絕發生在begin_request之前，轉RETRY_WAIT而不扣任務attempt。401/403與FinMind方案／授權異常隔離來源；429/503沿用共享冷卻。預設官方30／60秒、間隔2秒；FinMind200／小時、間隔2秒；這是候選保守設定，尚未證明是供應商正式額度或最佳吞吐。
3. 遠端7來源競爭測試40868944927：各來源兩工作競爭同一個測試額度，均只准一筆、另一筆延後，attempts均0。這測的是實際Git CAS預算控制，沒有送源站HTTP，不能代替供應商實際負載測量。同一run的缺件子工作因無入選案例而FAIL，保留原始結果，不改成全批成功。
4. 診斷40869660722：凍結TAIFEX 1845個待分類任務中，原門檻錯把未公布最早日期當成禁止查詢。已修正為：只有官方表單明確支援日期過濾、路由／起迄日／任務綁定正確才可查詢；availability_verified仍保持false，不宣稱該期間必有資料。已回空資料的舊版本、已存隔離檔、耗盡額度或未對帳中斷仍不直接重抓。
5. 修正後40870505597對2017-01 dlSingleOrderDown實際查詢一筆：回覆空資料，轉APPLICABILITY_HOLD，attempts由0增1，來源HTTP intent1，accepted=false；測試為FAIL／待查，不能算缺件下載成功。批次隔離動作正確，沒有全來源hold或改寫正式RAW。空回覆原文這次未另保存，仍是需補強的拒絕回應證據保存缺口。

Adapter目前類型仍有界限：TAIFEX缺件回呼僅CSV歷史查詢；TDCC缺件回呼為週持股歷史；NDC是已保存且SHA核對的官方源檔月份重建，未做新源檔發現；其他未識別類型仍隔離。不能宣稱所有歷史格式、年ZIP／PDF與所有財報類型皆已完成正式整合。

剩餘正式上線門檻：把可驗證的任務契約與舊斷點分批放行到正式worker（CLI production目前仍硬阻擋）；補上未支援類別／拒絕回應保存與有資料案例的端到端實測；實測來源配額、心跳與負載，再解除production與自動觸發。整個189521任務不是本批完成率分母，也不能承諾三天完成全庫。

證據：
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40868944927 （配額7通過、缺件選案子工作失敗）
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40869660722 （唯讀診斷）
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40870505597 （實際查詢空回覆，未接受）
- https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40875609531 （1606隔離回應重驗完成）
