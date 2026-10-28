# 單一入口合併驗收與依賴續跑（2026-10-28）

已實作的範圍：保留原件內容驗證、37 條／八組缺口統一彙總、失敗分流、既有跨來源證據輸入 SHA 重核、讀回原件範圍本機復原，以及獨立的一次性遠端 metadata 分頁盤點工作。

尚未實作／尚缺證據的範圍：核准全歷史母體、完整公告當時可得時間及版本、全部資料集完整契約、獨立上游與全量數值覆蓋、正式發布及下游真實回測。此入口不寫正式資料庫，不核准發布，不能稱八組全量驗收已完成。

## 本次實際執行

- 872 項程式測試通過，0 失敗／錯誤／跳過；測試器禁止非預期網路連線。
- 337281 筆登錄與補存版本混合清單掃描；不是核准母體或唯一觀察值分母。
- 562 筆內容證據按 RAW／archive SHA、任務上下文、來源依賴與日期市場證據續用；沒有重新解析這 562 筆。
- 舊跨來源診斷 298 個輸入參照重核 SHA 成功；19000 欄位對為既有歷史比對數，這次未重算數值，也未核准上游獨立性。
- 本輪讀回範圍 22 個檔案／包、562 筆原件參照完成獨立目錄本機復原 SHA；不是全庫遠端災難復原。
- 六個 2001Q1 MOPS BalanceSheet 原件均有當期隱藏欄位、公司表頭，但 bodyTable/tbody 沒有任何會計科目數值列。保留原件，改列 SOURCE_ROUTE_REVIEW；不能靠改解析器恢復空表，也不能據此推斷歷史財報不存在。
- 最終整合執行約 27 秒（保留快取、既有小範圍原件），不能外推為整庫耗時。
- 八組仍 0 完成、6 PARTIAL、1 UNKNOWN、1 BLOCKED；37 條全範圍規格均 UNKNOWN，明確列出尚缺條件；正式核准範圍 0。

## 複用方式

專案根目錄執行：

```bash
python -m scripts.v093_acceptance_integrated \
 --register /path/register --raw-cache /path/raw-cache \
 --out /path/new-output \
 --plan reports/raw-acceptance/20261028_acceleration_plan/execution_plan.json \
 --resume /path/previous-output/content/checkpoint.json \
 --esb-evidence /path/esb-evidence \
 --diagnostic /path/cross-source-diagnostic.json \
 --remote-snapshot /path/scoped-remote-metadata.json
```

每次使用新 output 目錄，保留上一個 checkpoint；復原目的地必須為空。第一個 V4 執行不沿用舊 V3 checkpoint，因為舊 token 沒有完整任務與依賴綁定；V4 後可逐鍵沿用。相關依賴改動仍會重驗，無關腳本不會使所有來源失效。共享解析器與 requirements lock 變更仍使其依賴結果失效。依賴圖為靜態 scripts imports 的保守閉包；若新增動態模組載入，必須同步擴充依賴登錄及測試。

輸出 integrated_summary.json、rule_results.json、group_results.json、content_triage.json、repair_queue.csv.gz 與 content/checkpoint.json。完整修補表依來源／資料集／年／月／期間／原件 SHA 留存，六個來源路由失敗與一般解析修補分開。

## 遠端 metadata 盤點

新增 workflow jarvis-acceptance-remote-inventory.yml；合併新 workflow 時單次啟動，或手動觸發，沒有新增週期排程。讀取既有 Google 授權，僅 files.list，從已知 RAW 根目錄精確選取 2000～2026 年及七來源（含 TDCC_ARCHIVE），分頁遞迴列舉 metadata，忽略年份層外的 canary。

單次 300 次 list 呼叫／480 秒預算，到上限保存 checkpoint 而非宣告完成；讀取出錯也保留未完成分頁。結果以 GitHub Actions artifact 留存，不改 Drive 原件、不下載來源市場資料。獨立盤點可用 --resume 接續 checkpoint。metadata 列舉完整不等於觀察值完整，也不是原件 SHA 讀回；多頁列舉不宣稱原子時點快照。

目前另有透過連結讀取的局部盤點，已確認 27 年份、189 個七來源資料夾（221 個年份直屬資料夾，包含輔助資料夾）；此結構證據不代表所有檔案已核對。

## 修補佇列口徑

237323 RECONCILE_LATEST：舊凍結清單候選，先對最新收據與母體。
99390 READBACK_EXISTING：本機未讀回，不是證明遠端未下載。
556 COMPLETE_EVIDENCE：有部分內容證據，其他規格待齊。
6 SOURCE_ROUTE_REVIEW：上述歷史財報原件為空數值表。
6 REVIEW_ESB_RAW_ONLY：興櫃原件保留，不進正式分析。

不把任一數量當作全庫缺失總數。未實作或缺證據的檢查明列 UNKNOWN，不以測試數、HTTP200、手填 passed=true 或舊報告標籤替代驗收。
