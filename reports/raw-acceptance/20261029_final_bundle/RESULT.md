# 上線前最後合併檢查與確定阻擋項（20261029 R11）

已把目前可執行的檢查合併成一份workflow，工作40880721668 SUCCESS。整個倉庫離線測試1039項通過、無略過；worker選定回歸146項亦通過，兩者有重疊，不相加。12份候選入口設定核對通過；12組production模式實際呼叫均在任何Git／來源操作前拒絕。

同批真正Drive測試：明確標示為非市場資料的53bytes拒絕回應測試內容，gzip壓縮後保存、讀回解壓、前後兩個SHA驗證通過；同內容重送仍同file_id。此測的是拒絕回應證據保存，不是市場資料下載或修復。來源HTTP0、正式RAW寫入0、deployment_ready=false。程式9955cd7df2323a3fc67ca5f5a76ed6876057922d。

修正：Executor遇到原生VALIDATE拒絕後，先保存任務隔離狀態，再由native adapter保留拒絕回應原始bytes（Drive gzip）與raw/stored雙SHA、reference、accepted_as_raw=false；Git只記收據，不放原始回應文字。存證失敗則保留原隔離狀態與安全錯誤分類，不冒稱保存成功。已保存的舊案例不回頭重新下載；新機制僅對之後執行的adapter生效。

## 確定還剩四個上線門檻

| ID | 真正未完成項目 | 完成條件 |
|---|---|---|
| G1 | 正式執行模式、舊進度分批匯入與可放行任務契約 | 目前production直接raise；須改成讀取核定契約、保留attempts與血緣、限制活躍任務量後執行真實native worker，完成正式入口閉環 |
| G2 | 必要來源類型與正向取件／補正／重驗 | 補齊本次範圍需要的格式（例如TAIFEX年包等尚未接通類型）；有資料的實際案例完成保存、讀回、校正與重驗；未知與空回覆保持待查，不造數據 |
| G3 | 持續接續與實際配額／效能 | 將已有durable dispatch接到正式worker與看門狗；真實工作負載驗證來源共用額度、Retry-After、心跳、lease接手及存放吞吐。既有7來源quota race只證明控制正確，不代表供應商吞吐已量測 |
| G4 | 固定版本發布及首批正式驗收 | G1–G3通過後合併固定版本；再查舊寫入者與ghost queue，單一寫入者切換，核對第一批正式資料與進度紀錄 |

這些項目不會因重跑目前已PASS的1039測試而自動完成；production拒絕是目前程式的實際行為，不是只差人工確認。不得把本workflow SUCCESS改寫成已能正式上線。

1602個歷史空回覆任務仍是待來源範圍查核，但可隔離管理；不要求它們全部查完，才啟動能安全執行核定任務的worker。全庫可用資料完整性與PIT仍分層追蹤。

## 保存與查詢

本批原倉庫完整測試log、1039項結果、新worker回歸log、12組正式門檻結果、拒絕回應存證收據，已由workflow自動保存Git與Drive並讀回SHA（7個結果檔）。Drive封存file_id 1lWhnELDOMGJxw9USICIT-pm0_qugz8ID；Git jarvis-source-preflight/record-40880721668-1-final-prelaunch/TWSE。報告sha 72480463de3d513f2568bd56648ae0f2e2a4d0c3dd9453748b6adae06f646dba。

完整執行：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40880721668 。機讀結果reports/raw-acceptance/20261029_final_bundle/full-repository-result.json。

前次證據仍留在Git固定版本、Drive檔案歷史與原RUN封存；本文件改為最新門檻，避免將舊狀態重複當成最新。新12條正式下載仍未啟動。
