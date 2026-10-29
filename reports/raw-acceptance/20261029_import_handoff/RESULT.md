# 七來源完整舊任務交接合併驗證（20261029 R5）

GitHub工作40845175656：success，7個來源保存＋7個獨立新環境讀回，共14個工作全數成功。程式版本e1546c6c7ae8c2270664ac8771ababc83d1bccd0。工作連結：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40845175656

| 來源 | 交接任務數 | 保存／獨立讀回 |
|---|---:|---|
| FinMind | 2711 | PASS |
| MOPS | 23512 | PASS |
| NDC | 322 | PASS |
| TAIFEX | 5061 | PASS |
| TDCC | 48059 | PASS |
| TPEx | 62814 | PASS |
| TWSE | 47042 | PASS |

合計189521筆，逐筆保留舊attempts與完整provenance，核對新definition、12槽唯一歸屬；7來源保存與獨立讀回的完整狀態SHA一致。重複匯入不覆蓋後續進度。數量是舊任務而非資料列，也不是內容驗收完成數。

本機合併回歸122項通過，12份預覽設定通過。第一批40845020271發現TWSE同一任務包含不同期間，保護機制阻擋該來源；修正為CONTENT_BLOCKED保留全部版本與PERIOD_CONFLICT標記，其definition.period僅沿用第一份紀錄作排序，不代表期間已確認。修正後完整新批通過。第一批失敗也保留在歷史紀錄，不改成成功。

此次匯入後的保守狀態：{"APPLICABILITY_HOLD": 189450, "BLOCKED": 59, "CONTENT_BLOCKED": 12}。APPLICABILITY_HOLD是待來源規則與舊檔核對，不能解讀為缺件；BLOCKED是舊重試預算耗盡；CONTENT_BLOCKED是內容或期間衝突待查。已保存舊檔須先核對後重用，不能重新全數下載。

測試狀態位於jarvis-source-preflight/import-40845175656-1/{source}；每來源的固定commit/SHA見remote-verify.json。正式jarvis-source-state未寫入，市場請求0、Drive原始資料寫入0、production_activation=false。

尚未完成：七來源實際執行器接12正式入口；來源適用性與內容驗證後逐批放行；有證據缺件的實際下載→保存→讀回→校正→重驗；正式來源共用限流與12槽負載；每次執行的自動GitHub/Drive驗收紀錄同步。不能宣告新12排程已上線，也不能承諾三天全庫完成。

加速：本次7來源平行而非逐來源等候；後續沿用未改動且已通過的控制測試，只重跑受影響項目。不得把所有歷史資料先驗完列為啟動的前提，但正式執行器本身須完成必要的端到端驗收。
