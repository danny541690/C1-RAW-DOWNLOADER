# 集保所真實缺件下載與中斷恢復（20261029 R6）

已新增真實來源小批測試，不重跑已完成的189521筆全量交接測試。選案僅限凍結紀錄中UNRESOLVED、所有版本無成功RAW參照、舊attempts小於3、且當日官方查詢日期選單仍提供的TDCC週資料；跳過已有RAW、已成功、官方空回覆、預算耗盡與未對帳中斷任務。

| 項目 | 結果 |
|---|---|
| 本機合併回歸 | 126項通過；12份預覽YAML通過 |
| 2026-09-11／6912／DESC | 真正下載缺件、不可覆寫保存到Drive隔離測試區、注入存檔後中斷；新runner讀回重驗成功 |
| 該筆內容 | 日期與代號相符，16筆持股分級通過原生格式與非負整數檢查；SHA一致 |
| 該筆舊重試紀錄 | attempts由1變2，沒有歸零；舊provenance保留 |
| 中斷恢復時的來源請求 | 0，沒有再次下載成功資料 |
| 2025-12-05／8042／ASC | 官方回覆查無資料，轉APPLICABILITY_HOLD；不是確認歷史不存在，也不算驗收完成 |
| 正式原始數據庫補正數 | 0；1筆新RAW已在隔離測試區通過基本驗證，尚未提升至正式月份資料夾 |

成功RAW參照1CcWmSimRC2QfCI_paDpfyS57wovWFLKO，SHA256=4cc9c75b8b4a74bb7825be00449e35182d36c85cb56fa37a18909f9b006b76e5。逐筆證據見remote-result.json與固定Git測試狀態jarvis-source-preflight/tdcc-missing-40853248163-1/TDCC。numeric_verified=false、pit_verified=false、full_acceptance=false，不能把基本格式檢查宣稱為全內容驗收。

第一批40853248163：FAIL，因第二筆SourceEmpty使整批提早停止，第一筆實際已保存；保留此失敗，不改寫成通過。修正正式executor加入ApplicabilityUnproven分類，官方空回覆隔離，不拖住其他任務；測試腳本逐筆續跑且保留成功項目。第二批恢復工作40853662597：SUCCESS，獨立runner完成第一筆讀回重驗並隔離第二筆，來源新增請求0。成功程式版本b69f462d5e9775e5cc434adf46fbcba954681277。

第一批中止前總HTTP計數未完整寫入case檔，因此總請求數標記unknown/null，不能沿用初始0；第二批0為實測值。第一批空回覆內容未另外保存，不能將它當作永久的官方缺件證明；須後續有證據的適用性查核。

證據：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40853248163 （第一批失敗）；https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40853662597 （恢復成功）。

剩餘上線門檻：七來源正式adapter與12入口接線；各來源適用性、既有RAW重用及有證據缺件的真實閉環；正式共同配額與負載；斷點/每次驗收結果自動回寫GitHub與Drive。TDCC本次是兩個候選的一筆基本驗證成功、一筆待查，其他來源不能據此宣告通過。新12條尚未正式啟動，舊排程沒有被重新啟動。
