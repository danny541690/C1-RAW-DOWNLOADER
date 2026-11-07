# JARVIS C1 v0.95 — R11 十二項缺失修正與小量驗證基準（2026-11-07）

> 只修改 v0.95 的規格、修正方案與唯讀測試，**不新增正式全史下載Cron、不變更正式Release Flag、不覆寫現有Drive原件**。
> 單庫 `danny541690/C1-RAW-DOWNLOADER`，Google Drive 架構表 `JARVIS_C1_v0.95_Architecture_Management_R1.xlsx`，89項問題總帳，R10 Run `42364261360`。

## 1. 三個硬決策
1. v0.95是唯一基準；v0.93僅做錯誤履歷與驗證演算法參考，不把它當新生產系統。
2. 16個下載類別（12雙向官方＋FinMind Free／Backer＋Daily＋Repair）和14個Bronze/Silver/Gold驗收分類是兩個軸，不能直接相加變30個常駐排程；維持1 Controller與動態少量Worker。
3. Bronze可獨立取得G0～G2正式可驗證歸檔，但Gold嚴格鎖定formula/PIT/asof/lineage；整庫release和bulk flag保持 `false`。

## 2. 十二項問題根因、改版及驗收契約

| 問題ID | 根因/症狀 | R11應採取修復 | 後續小量實測PASS標準 | 目前實作狀態 |
|---|---|---|---|---|
| P0-01 | 重複排程／16與14混淆 | 保留16類原始收集任務、14類處理／驗收，統一任務Ledger；不開30個常駐Runner | 試跑同鍵重複派發只生成1個正式工作與SKIP收據 | **SPEC_ONLY** |
| P0-02 | 多Runner爭搶、Drive非原子交易 | 採單一狀態仲裁與 CAS/Fencing；先傳內容定址原檔，再以受保護的狀態指標提交 | 兩Runner一勝一敗、過期鎖拒寫、中斷後恢復不重複發布 | **NEEDS_RUNTIME_INTEGRATION** |
| P0-03 | 不同Drive路徑被判遺失 | 建Canonical Manifest，列每個檔案Drive ID／來源／dataset／期間／stage／SHA／程式版與驗收範圍 | 9-11月已知原件全部索引對齊；跨路徑相同內容不再下載 | **NEEDS_REAL_DRIVE_PILOT** |
| P0-04 | 11/18來源月份有檔誤當61.1%完整 | 以官方當期合法dataset×交易/公告日×證券名冊建立expected分母 | 分母未知顯示UNKNOWN，未公告／來源不適用不算缺漏 | **PARTIAL_RULE_FIX** |
| P0-05 | 財報/景氣修訂導致前視偏差 | 公告發布日與版本vintage不可變，依decision_asof篩選；未查證直接禁用Gold | 時間旅行測試拒絕決策日期之後才知道的報表 | **NEEDS_FORMULA_LEVEL_EVIDENCE** |
| P0-06 | R6/R7定期跑卻零下載 | 逐dataset接入v0.95真實官方Adapter，只在契約驗證與CAS可用後啟用Bronze | 1個實際缺件完成HTTP→Drive SHA讀回→Checkpoint→重跑SKIP | **NEEDS_LIVE_SOURCE_PILOT** |
| P1-07 | 443欄位目錄不等於443可計算公式 | 逐項登錄formula digest、輸入、暖機、PIT、停用原因 | 完整定義才啟用，尚不完整必須DISABLED_WITH_REASON | **NEEDS_IMPLEMENTATION** |
| P1-08 | 候選血緣只做到SHA樣本 | 建立Bronze/Silver/Gold分區真實parent-child DAG與影響反查 | 已放行Gold都可追到上游內容SHA及計算版本 | **NEEDS_IMPLEMENTATION** |
| P1-09 | R6/R7及多個舊排程重做同樣驗證 | 統一錯誤問題ID，已有有效收據則SKIP，必要時只派異常的受影響分區 | 同來源同SHA同程式版本不再次掃Drive或重抓 | **PARTIAL_RULE_FIX** |
| P1-10 | Silver同名檔不同內容／Parquet小檔 | 輸出排序、決定性metadata、檔案內容SHA分版、按照市場與月適度合併 | 相同輸入/程式SHA完全相同；變版保留舊檔 | **OCTOBER_V2_PARTIAL_FIX** |
| P1-11 | TPEx ---與TDCC百分比被當下載失敗 | 來源語意驗證與transport/schema/value/PIT分流，保留原生異常 | TPEx 412原生行與TDCC 496群組可再查，不以填0消失 | **PARTIAL_RULE_FIX** |
| P2-12 | 完成率與成本不實、還原能力未驗證 | 按當次真實run量測取得／重用／修復／隔離、吞吐、配額與回復 | 每次給正確分母及Restore SHA證據 | **NEEDS_METRICS** |

### 狀態解讀
`PARTIAL_RULE_FIX` 或 `OCTOBER_V2_PARTIAL_FIX`：先前只在指定異常範圍已有程式修復，不應推廣宣稱所有2000–2026資料完成。
`NEEDS_RUNTIME_INTEGRATION`／`NEEDS_LIVE_SOURCE_PILOT`／`NEEDS_IMPLEMENTATION`：本輪產出規範與測試基線，不是已完成資料下載。
`SPEC_ONLY`：本輪已釐清並建立契約，實際調度器仍待落地。

## 3. 小量資料試跑：五次逐步擴充，不要一次全史

| 階段 | 試跑 | 最多資料單元 | 工作範圍 | 放行條件 |
|---|---|---:|---|---|
| T0 | No-network contract and regression suite | 0 | Validate 12 controls, 16 vs 14 taxonomy, output policy, PIT date logic and unknown completeness; no Drive writes | all static and fault-injection tests green |
| T1 | 2026-09–11 manifest inventory only | 3 | Cross-index known-good SHA in staging/canonical folder; find true missing as-of published dates | No previously accepted source bytes redownloaded; each claimed missing item links official expected release evidence |
| T2 | One exact missing Bronze native data unit | 1 | v0.95 adapter live HTTP → immutable Drive → SHA readback → Git CAS checkpoint; simulate duplicate and crash | one committed identity, 100% hash readback; second attempt REUSED; stale runner cannot publish |
| T3 | One Silver + one Gold lineage pilot | 2 | Transform verified parent; use a genuinely PIT-certifiable indicator, verify reverse and forward lineage | code+formula digest, source SHA and asof assertions; noncertified indicator disabled |
| T4 | 6-work-unit bounded historical Bronze canary | 6 | Two sources, known eligible dates, use known good skips, write only provable gaps; no automatic 27-year advance | all tasks accounted, rollback/restore, zero duplicate accepted objects, explicit failed units |

### 先試的資料建議
- T1：2026年9、10、11月既有TWSE/TPEx/MOPS/TDCC/TAIFEX/NDC各來源路徑與SHA索引，只處理元資料，不重新下載已通過檔案。
- T2：從現有已核對官方真正可取得的缺件中**實際選出1筆**，不預先假設特定股票/日期一定缺件；測試真正v0.95來源Adapter加分區鎖、不可變Drive寫入與回讀。
- T3：選該筆已驗證來源可衍生的1個Silver，再選1個有充分前序暖機與PIT證據的Gold。若暫無合法Gold樣本，以Gold disabled為正確結果。
- T4：最多6筆READY（各來源至多一個Writer），失敗隔離不拖住其他工作；核對源請求數、SHA、成功與例外、下一批checkpoint。

## 4. 工程控制與驗收語意
- **不能把GitHub Action成功當作資料完整或PIT PASS**。一個工作必須有官方可用性、原始回應hash、Drive檔案ID、讀回hash、parser/schema、checkpoint lease/epoch及子分區狀態，才能標記相應階段驗收。
- 沒有官方expected分母，完整率必須UNKNOWN；不是0或100%。市場歷史名冊包括退市股票及當時上市/櫃轉換。
- TPEx 412筆`---`和TDCC 496異常群組是**資料語意**，不要當作網路故障來無限重抓。
- v0.95分區採原生不可變原件、stable Parquet衍生物、受保護Manifest+版本發布指標；禁止在每個輸出中寫執行當下日期而引起不可重現內容。
- 不需引入Kubernetes/Spark/Kafka/Airflow等重型平台；Google Drive並非ACID資料庫，跨Runner狀態應由單一CAS仲裁。
- 每個T階段產出Run ID、原始/轉換SHA、成功/跳過/失敗、測試耗時、容量/配額、發布限制及下一步；沒有完成的證據不可提前改status。

## 5. 已交付/後續邊界
- 新設定 `config/v095_r11_improvement_and_pilot_plan.json`：十二項根因、修復及五階段測試。
- 新唯讀Gate `scripts/v095_r11_plan_contract_gate.py`：檢查16/14架構、發佈鎖、未知分母、範圍限縮、SHA/Run憑證及PIT。
- 新測試 `tests/test_v095_r11_plan_contract_gate.py`：8項錯誤注入，確保規格不會偷偷變成大量下載。
- Workflow `.github/workflows/v095-r11-architecture-improvement-pilot-gate.yml`：Push/手動執行測試，**沒有Cron，沒有Drive修改權限**。
- 仍需做的 T1～T4，待使用者提供小量測試或選定已查證缺件來源後執行，不把規格驗收當作生產修復。

## 6. 專業依據
Microsoft Fabric Bronze/Silver/Gold：https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture
Microsoft Idempotent Consumer：https://learn.microsoft.com/zh-tw/azure/architecture/patterns/idempotent-consumer
Microsoft Competing Consumers：https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers

## 7. 不更動的正式生產旗標
`governance/v095/PHASE1_FLAGS.json` 應保持：`BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`、`last_evidence_verified=false`，直到分區級Bronze生產寫入、真正跨Runner防競爭、來源適用分母、分階段發布證據被核准。
