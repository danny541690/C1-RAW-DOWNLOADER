# JARVIS v0.97 R3｜正式切換執行規格與驗收 SOP（2026-11-18）

> 核心結論：R3 四項核心規則已接入測試分支並完成回歸／真實70筆檢查；**正式資料寫入器、正式 G5 發布、舊版退役與官方 per-file 契約證據仍未完成。** 目前不得宣稱正式上線。這份文件是正式部署的驗收規範，不是完成證明。

## 0. 不可變更的需求與母體

- 系統角色：ChatGPT 決策；GitHub Actions 運算與協調；Google Drive 永久儲存與證據；原始 Bronze 唯讀。
- 固定母體 74,750：TWSE 12,071；TPEx 13,200；MOPS 1,935；TDCC 40,384；TAIFEX 3,140；NDC 320；FinMind 3,700。
- 只有上市／上櫃；日以上盤後資料，數值一律億元（正式分析層標準；驗收原始資料保留原單位）；不使用分點逐筆／主筆交易。非個股控制檔及官方總表須分類，不得誤判毀損，也不得直接計為可分析個股。
- **絕不執行 Silver/Gold 實體轉換**；Silver Ready 意指驗收合格、將來可轉換。
- 再跑時以 SHA、來源 ID、規則/模板/解析器版本、依賴 digest 驗證可重用證據；已驗收原檔不重抓、不改寫。規則有變才重新驗。
- 禁止把 `CANDIDATE`、`HEADER_MATCHED_UNCERTIFIED`、`EVIDENCE_PENDING`、`CHECKED`、`PENDING`、歷史 READY 等同正式 R3 PASS。
- 每個 record 必須最終對帳為一個明確狀態；正式 READY 必須有逐筆 G1-G5 有效證據和 G5 遠端讀回。來源尚未可取得的官方材料可 HOLD／PENDING，但不得捏造、零值填補或卡死其他來源。

## 1. G0：R1／V3／G2G3 安全寫入交接（先行硬關卡）

1. 唯讀盤點 `.github/workflows`，含17個非共用凍結 Workflow、8個 cron 及非 cron 的自行 redispatch；先列出所有可能觸及 Drive Master／Checkpoint／Error Ledger 的入口。
2. 建立不可變交接快照：R1 最新 Master、V3 最新 Master、相關七來源 Checkpoint、G2/G3 正式 registry、G4 mapping checkpoint、錯誤及歷史；紀錄 Drive ID、檔名、SHA256、Run ID、規則版次、時間及檔案數。快照須上傳新命名空間並讀回確認。
3. 僅當新的 R3 完整資料路徑、簽證 writer、正式測試均通過後，才對 **所有舊寫入入口** 進行原地退役：停止 cron、workflow_dispatch 自派發、watchdog 恢復；不能只關閉一個 Cron；不改動原始證據。
4. 等待在途 Run 全部完成；至少再次讀 GitHub 最新 Runs + Google Drive 快照，確定沒有遲到的舊版本寫入。不能單純依賴不同 workflow 的 GitHub `concurrency` 名稱。
5. 發布 R3 單一 writer fence：只能由一個持有有效 fence 的 R3 Master writer 發布不可變的 G5 總帳。GitHub R3 writer 單組 concurrency；每次發布再次檢查 fence／舊版排程無活躍寫入。CAS／鎖失敗即停，不重試成重複檔。
6. 任何前述條件未達成，`G0=HOLD`，不啟動正式 Master、更不改 Bronze。舊版恢復方案必須有書面回滾記錄、不得與 R3 併行寫入。

## 2. G1：原始搬運與血緣完整性

- 來源途徑A：官方來源 → v0.93 原檔 → v0.97 Bronze；途徑B：官方來源 → v0.97 Bronze（直接下載）。不可把只檢查 v0.97 自己的 SHA 說成「官方源頭認證」。
- 凍結 source_id、source、目的檔 Drive ID、版本與來源鏈；計算真實目的 bytes SHA256，與來源鏈原始 SHA、0.93 搬運收據逐段比對。
- 每次核對檔案大小、非空、ZIP 成員 CRC/SHA（不是只看 ZIP 能打開）；缺少官方來源證據與 bytes mismatch 必須分開列原因。
- SHA 一致只代表 byte integrity；來源身分、歷史年代、文件發布時點仍由 G2/G3 認證。
- 無法讀取、損毀、hash 不一致：HOLD + 錯誤履歷；重試僅限可恢復 I/O 錯誤，最多3次；原始檔不可自動修正或覆蓋。

## 3. G2：官方歷史 Dataset／Era 契約

- 驗收單位是 **(source,dataset,era,official_edition,member_layout)**，不是僅七來源各一個萬用格式，也不僅檔名副檔名。
- 契約必須記錄：起訖日期、有效版本、官方資料集網址、文件/回應 SHA、原始時間與發布 as-of、原始欄位/表頭/身分 ID、必備/可選欄位、已人工或獨立查證的別名映射、不可憑空推定的變動。
- 有歧義時相似度只可做候選 discovery；沒有正式官方文件與完整 native 文件格式證明就是 HOLD。
- TWSE／TPEx 注意 2000–2007 歷史日行情來源及混合表/商業版規格，MOPS GAAP/XBRL/iXBRL 與公告修正 PIT，TDCC 16/17級距與特殊證券身分、429股/20%差異檔，TAIFEX 日夜盤交易日，NDC Excel 原始儲存格／方法改版，FinMind dataset ID／版本與資料提供方修訂。
- 現有 143 candidate specifications／272 grouping groups 不是正式已核准 per-file contracts。必須存正式 evidence ID 並依 SHA+版本逐筆綁定。

## 4. G3：官方格式最小解析／全部必要語意

- G2 有效才可進 G3；原始檔全檔檢查，而非只有第一行表頭。解析必備欄位完整、交易/公布日期、型態、主鍵、空值、原始單位與證券歷史身分。
- 遵守資源上限；ZIP 必須逐成員驗證，PDF/HTML/XLS/XLSX 按原生契約，不得用空白或模擬資料補歷史欄位。
- 完整掃描結果附 parser_version、g2_contract_version、source SHA、源檔 ID、缺失欄位、錯誤數、原始證據 ID。
- 有未識別必要欄位或多種可能語意就 HOLD；可保存 CANDIDATE，但不可核 PASS。

## 5. G4：Silver 輸入契約（不做轉換）

- G1/G2/G3 正式通過後才驗證 G4。
- 每個目標欄位都要可從已認證 G3 的來源欄位建立一對一或明確可追溯、版本化的對應；驗證型態、單位換算規則、時間基準/發布 PIT、歷史證券類別、市場、有效日期、上市櫃範圍、缺值策略、數值原始語意。
- 可建立「輸入結構/映射證明」JSON，但禁止建立實際 Silver/Gold 資料表。
- `HEADER_MATCHED_UNCERTIFIED` 是候選，非 G4 PASS；資料缺少即 HOLD，不得跳過某個 Gate。

## 6. G5：唯一正式總帳與兩階段提交

1. G1～G4 全部正式 PASS，原版式/來源 digest 及 gate dependency digest 可重用。
2. 建立候選逐筆 G5 certificate：source_id、source、原件 SHA、G1～G4 evidence SHA、規則版次、writer_fence、狀態、固定 `silver_materialized=false` / `gold_materialized=false`。
3. **候選不等於 PASS**：寫入不可變證據至 Drive → 再獨立 GET 讀回 → 位元組或標準 JSON digest 完全一致 → 標記 G5 PASS；模擬 reader 回傳不算。
4. 依七來源獨立 shard Checkpoint，寫入 Delta/錯誤履歷，讀回成功才更新正式狀態；每筆一次最終 disposition，重播必須冪等；重複 source ID、異常 SHA、版本錯位、幽靈記錄立即停止該來源，不影響其他來源。
5. 單一 writer 最後合併 74,750 source_id，七來源數量逐一對帳，分離 `SILVER_READY/HOLD/EXCLUDED/NOT_APPLICABLE/PENDING/RETRY`；進度要分開呈現「已讀」、「已檢查」、「已結案」、「Ready」。
6. 必須保留每一版不可變 Master + Error Ledger + Report + execution history，再以安全可驗證的方式更新 `R3_MASTER_LATEST`；成功後再次比對新 Master ID、SHA、Version、Run ID、fence，不能覆蓋其他系統總帳。

## 7. 併發、續跑、測試、故障規則

- 執行：七來源互不阻塞，可按源內 shard 分工；只有 G5 單一 writer 更新正式總帳，失敗來源列 HOLD／RETRY，其餘來源繼續。
- 正式測試順序：70真實 → 700真實整合 → 1000真實切換/失敗重播 → 74750固定 cohort 帳務核對；合成 700/1000 不能取代真實測試。
- Checkpoint 增量以 source_id+SHA+gate+rule/template/parser/dependency_digest 精準比對，可重用的 PASS 不重算。
- transient 網路/Drive/API錯誤退避重試最多3次；模板、缺少官方證據、語意歧義永久 HOLD，不無限重試；watchdog 只在有 pending/可重試項目及合法 writer 時喚醒。
- 每批正式結果存 Drive，保留錯誤總帳分類、修改紀錄、每來源報表、Run ID；任何無法核實不得直接跳至 READY。
- 退出：七來源皆已明確 disposition，總帳 74,750 精準對帳，沒有未記錄的例外，且只有逐筆 G5 PASS 可以 counted as READY；未滿足則如實維持 BLOCKED/HOLD。

## 8. 2026-11-18 已執行與未完成

- 已實作隔離分支：`scripts/v097_r3_formal_release_contracts.py`（G0/G2/G3/G4/G5 純規則）、`scripts/v097_r3_live_handover_audit.py`、`scripts/v097_r3_live_contract_census.py`、`scripts/v097_r3_real_formal_70_pilot.py`。
- 先前真實 Run 44237115837 成功：70/70 0.97 目的檔 SHA 與凍結基準一致、隔離 Drive 測試收據讀回成功。
- 新整合 Run 44239132913：測試 G0 實際偵測 R1 44238793609 / V3 44239022498 在途、八個舊 Cron 未停。七來源 R1 G2/G3 正式憑證 registry **0筆**；已讀 G4 header candidate 共83筆，未認證。70真實檔案經新正式 G2/G3/G4 核驗：70筆皆 G2 HOLD，後續 G3/G4 因依賴不足 HOLD；不是 Bronze 毀損。
- R3 沒有正式總帳，沒有 R3 READY；尚未執行正式源資料全量實際接手與正式 G5 發布。舊系統保持原狀以避免中途資料遺失。

## 9. 上線硬放行條件與命令

**只有在**：G0 舊工作停止＋已封存快照＋唯一 writer fence；G1 官方到0.97 完整血緣實測；G2/G3 每個正式可核模板和 native 證據通過；G4 真實輸入對映；G5 受控真實 Drive 測試讀回與重播、70/700/1000 實測和全量母體對帳，才允許正式 R3 writer 發布。

當前 R3 的一鍵工作是**整合前測**，不是正式發布器；不能以其成功作為解除 G0 HOLD 的依據。目前保留 Draft PR #61，不合併正式主分支、不停舊版排程。

建議 ChatGPT 一次操作指令（會自動逐關執行並在硬門檻不符時停止，不得偽造 PASS）：

```
賈維斯，執行 JARVIS v0.97 R3 正式切換準備與上線驗收：
以 GitHub danny541690/C1-RAW-DOWNLOADER 的 R3 staging 分支與 PR #61、
Google Drive 最新 Checkpoint 為準，先完成 G0 R1/V3/所有 G2G3 舊寫入入口快照、
正式來源及歷史模板補證、G3完整原生解析、G4 Silver輸入映射和
G5獨立不可變憑證及單一 Master 的正式 writer 實作。
連續執行70/700/1000真實整合測試並完成74750筆固定母體清冊對帳；
每項缺失增量修復，錯誤重試最多三次，歷史官方不可驗證者 HOLD。
在 G0-G5 真實放行條件全部通過以前不得停掉舊系統、
不得合併發布 PR、不得出現正式 R3 READY；
全部通過後執行快照→停止舊派工/自派發→等待在途Run退出→
取得唯一writer fence→R3正式驗收→G5持久化/讀回→MASTER發布與對帳。
Bronze只讀、Silver/Gold一律不做實際轉換。全部報告、錯誤和歷史存Google Drive，
最後回報正式Run ID、每來源及每Gate完成率、正式READY數、HOLD原因、Master及證據路徑。
```

**此指令是啟動部署流程的規格，不代表現已滿足正式放行條件或可即刻宣告上線。**

## 10. 官方文件覆核新增的時間邊界修正

- 臺灣期貨交易所正式沿革確認夜盤 **2017-05-15** 啟動，不能把「2017-05」整月都當成夜盤上線後；既有月份級 period registry 只能供候選選取，G2 正式核證必須用精確日界及契約/日夜盤分類。官方來源：https://www.taifex.com.tw/cht/4/historyOfTrading
- 證交所 IFRS 官方說明：上市上櫃一般自 **2013 年** 開始採 IFRS，但前期採用及特定公司發生差異；G2 不得單靠 2013 年界線直接宣告某個公司的報表口徑，須依實際公告及採用期。官方來源：https://www.twse.com.tw/rwd/IFRS/aboutIFRS
- TDCC 官方查詢說明：歷史股權分散表自 **2008-07** 起建置，公開查詢保存期間一年；2008 年之前與更久歷史 archive 的來源與修訂版次必須依 v0.93/0.97 保存的正式證據驗證，不可因目前網頁查不到就判檔案損毀。官方來源：https://s.tdcc.com.tw/portal/zh/smWeb/qryStock

以上三點證實「月份級歷史分期」只夠做候選排程，不夠自動核發 G2。R3 的正式模板必須採 dataset/edition/day-level proof 且連結官方文件、原生欄位及 PIT 時點。
