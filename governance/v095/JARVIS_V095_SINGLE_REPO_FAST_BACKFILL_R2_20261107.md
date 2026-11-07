# JARVIS v0.95 — 單一 GitHub 庫 2000–2026 最短時間正確建置方案（R2）
日期：2026-11-07。唯一 GitHub 執行庫：`danny541690/C1-RAW-DOWNLOADER`。此庫目前為 **PUBLIC**；不得存入個人持倉、私人投資策略、原始授權憑證、含敏感檔案 ID 的資料、或任何未經允許公開的研究。若要把私人策略放進同一庫，必須先將整個 RAW 倉庫改為 Private，檢查歷史 commits/Actions artifacts 及外部 Fork 的暴露；不能只在 README 說是單庫。

## 0. 已查證實際現況（非推測）
- [ULTIMATE R1](../../.github/workflows/v095-ultimate-r1.yml) 每15分鐘啟動 14 concurrent evidence lanes，另有 Pilot Controller 和三個月整併；[Run 42328008762](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42328008762) 16/16 Jobs success，14 lane receipts 與 Drive 真實上傳/讀回 SHA 成功。
- 其 `scripts/v095_ultimate_r1_14lane_worker.py` 對多數資料執行 **候選查驗**（writable_data_mutation=false），並未自動下載全歷史缺檔或生成全部 443 Gold。
- `scripts/v095_ultimate_r1_controller.py` 觀察到 2026-09～11 的六來源共 11/18 個「來源月份有檔」格子。這不是六來源資料集完整率，也不是 PIT 完成率。
- `scripts/v095_443_bidirectional_lineage.py` 產出的是血緣候選；使用 domain hints，不能視為每一指標公式/父分區已驗證。
- `governance/v095/PHASE1_FLAGS.json` 仍將 `BULK_COPY_APPROVED` 和 `RELEASE_APPROVED` 設為 false。R2 規劃禁止修改這些 Gate 以假裝完成。
- `config/v095_ultimate_r1.json` 已備 14 Lane、候選 Driver、六來源及 443 目錄，應「擴充既有程式」而非從零再造或新建第二套實際下載排程。

## 1. 執行架構與單庫權責
ChatGPT 指令/驗收判讀 → 單庫 RAW GitHub Controller（1）→ READY 任務派給可用 14 槽（Bronze 6／Silver 4／Gold 4）→ Drive（Bronze、Silver、Gold、不可變 receipts、Checkpoint）→ Controller 依 QA/PIT/雙向血緣 Gate 決定 RELEASE。
所有程式版本、契約、測試、運作紀錄的**程式碼**僅留在 RAW 庫；所有大型市場資料、帶憑證資訊或敏感的非公開資料留在授權 Drive 資料夾。若需私人策略，須把 RAW 倉庫改為 Private，而非把 C1-JARVIS 私有程式直接合併到公開 RAW 庫。
唯一可寫入正式資料的 Writer 應持有 lease+fence；14 槽能「負責」不代表 14 槽應同時寫同一份 Manifest。只允許 Controller／Committer 單一原子更新正式指標。

## 2. 最短時間的調度（避免 14 槽空轉）
1. 15分鐘一次 **單一 controller** 檢查 durable manifest（有條件地省略空矩陣），以 `task_id=(source,dataset,market,period,partition,schema_version,source_revision)` 去重。
2. 「來源允許、PIT 截止時間已到、輸入資料已通過上游 QA、資源額度可用」才建立 READY。未到官方可取得日期不是「下載失敗」，也不列入分母。
3. 初期真實處理 6 個並行 Runner，依監測指標逐階增加 8→10→14；Drive API request/sec、來源封鎖／429／5xx、QA latency、衝突率及 budget 任一超標即退回上一級。原 R1 的 14 全量每15分鐘掃描先維持候選檢查，正式 R2 切換時必須在同一提交停掉重複 14 個全量檢查 cron，改由唯一有 READY 才 dispatch；避免雙 scheduler 併行。
4. 來源六槽：TWSE、TPEx、MOPS、TDCC、TAIFEX、NDC；FinMind 免費版只在等價契約／法規允許且官方缺口確立後補缺；缺法定歷史來源即標記 NO_HISTORICAL_SOURCE，不能生成虛假的空白資料。
5. Silver 四槽：價格量、財報與法人、TDCC、期貨與總體；Gold 四槽：技術、籌碼、財報估值、跨市場。Silver/GOLD 在 Bronze QA 以前不能搶跑。
6. 優先序：2026/09 P0 真實修復 → 2026/10、11 pilot → 每日最新增量更新 → 由新到舊回填，同時由舊到新查缺。以已通過月份為 checkpoint，不重抓正確內容。
7. 減少小檔 I/O：以月分區/來源批次取得，Bronze 原始 bytes immutable；Silver/Gold 的重新計算只有輸入 SHA、公式 digest、PIT cutoffs 或依賴改變才觸發；月／日不適用的資料只記狀態，不補零。
8. 對有限來源加 rate-limit / jitter / exponential retry：15、30、60 分鐘最多 3 次；Schema drift、PIT UNKNOWN、checksum conflict 進 quarantine，繼續下一任務，不能無限困在同一月份。更新 state 需 CAS + lease/fence。
9. 原始資料可重用舊 v0.93 **不可變 bytes**，但每筆必須重新算 SHA、核對 source/日期/標準契約，驗證未通過不升格；絕不把 v0.93 的 PASS 直接繼承為 v0.95 PASS。

## 3. 三層驗收與指標
- **Bronze**：來源文件真實 bytes、日期、欄位、單位、日曆、大小、來源版本、SHA256；遠端讀回再次 SHA；原始檔不可覆寫。重要缺漏與異常保留，不偽造資料。
- **Silver**：原生格式→型別明確 Parquet，商品代碼/市場別/交易日/主鍵唯一，欄位/單位/符號/合理值/重複檢測；與 Bronze 行數與法定例外對帳；每筆輸入引用 Bronze SHA。
- **Gold**：443 指標各有唯一 ID、公式/版本 digest、最短暖機期、輸入欄位與 SHA、歷史 as-of、合法空值條件；無足夠來源時設 `DISABLED_WITH_REASON` 不宣稱 443 全部計算成功。
- **PIT**：每筆 `observation_period`、`first_published_at`、`available_at`、`downloaded_at`、`revision_at` 分開，`available_at<=decision_asof`；停復牌/下市/歷史成份股、除權息、財報公告與後來修正需 as-of；未知日期一律 BLOCK，不能回填今天已知的歷史數值。
- **雙向血緣**：Gold row → 指標公式/版本 → Silver row + sha → Bronze record + sha → source/公告版本；反向 Bronze record → 下游所有 Silver → Gold → View / strategy indicator。每個邊有父/子內容指紋、row/partition ID、run ID；主鍵/單位/時間戳的 join 一致。沒有 orphan/cycle、SHA mismatches；抽樣/全量覆蓋率記在報告，非推測 100%。
- **原子發布**：僅 PASS partition 可切 latest pointer；前版快照保留以便 rollback；沒有 PIT 的 Gold 只能是 CANDIDATE，不能當歷史正式研究資料。

## 4. 歷史範圍與驗收分母
範圍 2000-01～2026-11 共 **323 個日曆月份**，但不能拿 323×6 當每來源實際可下載「應有資料」。以資料集初次發布、交易日曆、停牌、公司上市日期、官方歷史可取得頁面、月報/季報公告日建立 expected/applicable 清冊：
- expected = 官方可取得且應涵蓋的 dataset × observation date × market/security universe as-of；
- verified = 真實 bytes/SHA/QA/PIT/lineage 全通過者；
- coverage = verified/expected；沒有官方分母顯示 UNKNOWN，不能當 0% 或 100%；
- separately count not-yet-due、not-applicable、official-unavailable、transient-fail、quarantine、PIT unknown。
全系統每輪回報已檢查、已下載、重用、已驗收、異常、隔離、待處理、耗時、請求數、流量/容量與 SHA。

## 5. 首輪切換前安全門檻（不可省略）
A. 完成 2026/09 TPEx OHLCV 412 非數值資料分類，不把 412 當 Silver→Gold 缺漏；P0 五類全部有真實修復/不可修復分類證據。
B. 2026/09 六來源已發布且符合契約的資料：Bronze→Silver→PIT→Gold 真實逐分區跑通，包含雙向血緣及 Drive 讀回。
C. 2026/10～11 同等 Pilot + release maturity 依官方發布可得性驗收；不因最近月份未到期而強行追求 18/18。
D. 443 catalog 每個指標有 formula_version、DAG、PIT/暖機與停用原因清冊；不必每筆均有可算數值，但每項都需可判定。
E. GitHub Durable Checkpoint 跨 Run CAS + lease/fencing + 斷線恢復、Drive 不可變讀回、重試不覆寫完成資料，具真實故障注入證據。
F. 設定 source monthly availability and versioned contracts；保障 2000 年歷史前缺資料不被誤標失敗。
以上未經驗證之前，`BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false` 保持，禁止宣稱 2000–2026 正式回填已開始。

## 6. 實作與上線順序（減少浪費）
- 第 1 次變更：凍結「來源契約/manifest/checkpoint」檔案版本，盤點 14 lane 現有能力與合法原生來源 Adapter，建立每一來源/期間缺口清冊；並保護已完成分區與歷史 bytes。
- 第 2 次變更：在單一 R1 Controller 旁加 queue planner / checkpoint CAS（先 READ_ONLY），使用已記錄的真實九月資料驗證，試一次 Crash Recovery。
- 第 3 次變更：九月 2026 的小量 E2E：Bronze SHA→Silver Parquet→Gold MA5/法人/月營收示例→PIT→雙向血緣；自動擴展到所有適用來源和已啟用公式。
- 第 4 次變更：逐步由 6→8→10→14 真實並行，記錄每單位成本和 429/503，達成穩定才切 full months。保留每日增量優先，使用舊正確資料重用和 gap-only repair。
- 第 5 次變更：發布全期驗收報告（每來源/年度/月份），不需所有來源 2000 年都有檔，但每一個 applicable partition 有 PASS 或經驗證例外。
R2 的設定檔 `config/v095_single_repo_fast_backfill_r2.json` 目前只定義**安全規格**，並未改動舊 `v095-ultimate-r1.yml` 的正式 Cron，也沒有啟動任何 2000–2026 全量下載。

## 7. 用一句話衡量進度
「截至日期，官方可取得的適用分區有多少已經被證明符合資料契約、SHA256、PIT、正向/反向血緣，是否能由特定 Gold 結果逆推出 Bronze 原始檔與官方公告時間？」如果證據缺一項，成品不能宣稱 PASS。
