# JARVIS C1｜DAILY 資料異常隔離與自動恢復 SOP v1.0
**核准日期：2026-10-14｜狀態：治理規則採納、程式參考實作已提交；實際 DAILY 管線接線與 E2E 尚未驗收。**

## 0. 優先序與適用範圍
本規則補充 `docs/C1_DATA_QUALITY_GOVERNANCE_v1.md`（DQ-001～016），不得取代既有證券身分、PIT、資料來源契約及 Production Gate。適用上市/上櫃日更Raw、技術、量能、法人、分點、TDCC、財報、類股共振、個股持股監控、回測。興櫃保留Raw不參與第一版分析。任何新來源/新指標必須按本SOP驗收。

**最高原則：Fail Closed for Signals; Continue for Valid Data.**
- L0 Raw不可刪、不可覆寫；錯誤值原樣保留，修正版以新批次/版本附加；記錄 SourceID、RawBatchID、SHA256、RetrievedAt、AvailableAt、RunID、原因碼與證據。
- 可信資料繼續運算；不可信欄位只阻擋依賴該欄位的指標、股票、日期或類股；不擅自補0、不猜收盤價、不以前一日假裝今日。
- 已持有股票即使隔離，也必須保留在持股風險畫面，標示「資料異常／不可產生新訊號」，不可靜默隱藏。
- 若市場/來源整批異常，阻擋受影響模組、類股廣度、法人同買與候選發布；不允許因剩餘可分析股票多而掩蓋系統性缺口。
- 無資料不等於錯誤：非交易日、正式停牌、零成交、財報未公告、TDCC尚未到週更新時間，必須按官方行事曆、交易狀態、公告/可得時間判定。

## 1. 三級分析狀態（獨立於既有 QA 判定）
| 分析狀態 | 意義 | 選股與回測 |
|---|---|---|
| PASS / FULL | 股票/當日/所需特徵通過QA、PIT、身分與來源契約 | 允許對應特徵與已核准策略 |
| PARTIAL | 部分特徵缺失/警告，但其他特徵獨立通過 | 僅允許白名單依賴的特徵；不得產生需要缺失特徵的「完整共振」訊號 |
| QUARANTINE | 核心價格/身分/公司行動/必要來源不可靠，或重大異常 | 禁止受影響訊號；Raw仍保留 |
既有QA判定 `PASS / PASS_WITH_WARNINGS / INCONCLUSIVE / FAIL` 不變；`INCONCLUSIVE/FAIL` 的相關資料絕不可提升成 FULL；`PASS_WITH_WARNINGS` 只能按逐欄核准的使用白名單映射PARTIAL。未核准來源/未確認身分一律不得進正式選股。

## 2. 異常分類與預設處理
| 原因碼 | 事件 | 預設動作 |
|---|---|---|
| HALTED_OFFICIAL | 官方停牌/停止交易 | 保留事件；禁當日新買進訊號；歷史標籤保留 |
| NO_TRADE_OFFICIAL | 合法零成交 | 禁突破/量能訊號，不捏造OHLC；依來源契約決定可用其他特徵 |
| NON_TRADING_DAY | 非交易日 | 不期待每日交易列；不當作抓取失敗 |
| CORPORATE_ACTION_PENDING | 除權息/減資/股本變更未核對 | 隔離受影響價格、報酬、量比、股數衍生特徵 |
| PRICE_MISSING_OR_INVALID | OHLC缺值、價格邏輯錯誤 | 隔離價格依賴指標與完整買進訊號 |
| INSTITUTIONAL_MISSING | 外資/投信/法人缺失 | 價格技術可用；法人同買、籌碼共振不可用 |
| OWNERSHIP_NOT_YET_PUBLISHED | TDCC週資料未公告 | 沿用最近**當時已公告**快照並顯示日期/新鮮度；不得當作今日觀測 |
| FINANCIAL_NOT_YET_PUBLISHED | 月營收/財報尚未公告 | 只用當時最新已公告版本；無可得值則缺值 |
| SOURCE_OUTAGE | 來源逾時/429/5xx/結構改版 | 有限重試、節流；仍失敗則隔離受影響資料/模組 |
| DUPLICATE_OR_CONFLICT | 重複鍵/跨來源衝突/單位異常 | 保留原始版本；核對口徑前不發布 |
| IDENTITY_UNVERIFIED | 當日上市櫃身分/證券種類未驗證 | QUARANTINE；興櫃按RAW_ONLY |
| PIT_UNVERIFIED | AvailableAt/KnowledgeDate不足以證明當時可用 | 禁止歷史回測/正式訊號 |
| BATCH_COVERAGE_DROP | 來源預期覆蓋突然顯著下降 | 整批或分市場/分來源阻擋；覆蓋門檻需由基線測試核准 |

## 3. DAILY 執行序
1. 接收不可變Raw；保留HTTP/CSV原文、參數、雜湊、來源、日期、時間、RunID。
2. 核對交易日、當日有效證券身分、停復牌/公司行動、欄位型別、單位、NULL、重複、OHLC區間、量值口徑與PIT。
3. 來源可恢復錯誤採**有限重試（初版建議一次）**，遵守官方速率限制與退避；不能為通過測試任意替代端點或日期。
4. 產生每一欄位的 `quality_status`、`reason_code`、`available_at`、`lineage`；依指標依賴圖（feature dependency graph）判定可計算集合。
5. 股票層 FULL/PARTIAL/QUARANTINE；模組層 `PUBLISH / PARTIAL_PUBLISH / BLOCK`。類股分母必須是當日經驗證可比較的合格宇宙，並揭露排除數與比例；覆蓋率不達核准門檻則禁止族群廣度/同買排行。
6. 發布DAILY品質摘要：預期/收到/合格/部分/隔離數，分來源/市場/類股缺值率、重試、原因碼、持股例外、版本、PIT、發布Gate；不得只顯示成功檔數。
7. 隔離資料保留待補；來源恢復後以**新版本**重抓、重驗證、重算受影響日期及下游滾動視窗，通過全部必要Gate才自動重新納入 FULL/允許訊號；留存狀態轉移與回補時間。不得修改原始歷史快照，歷史回測仍以當時可得資料版本重播。

## 4. 回補/復歸明確門檻
`QUARANTINE → PARTIAL → FULL` 不是單純資料非空即可：需 (a) 來源契約已核准、(b) 身分/公司行動/交易狀態核對、(c) 型別與邏輯QA通過、(d) PIT/新鮮度通過、(e) 指標暖機視窗足夠、(f) 依賴指標重新運算、(g) 回歸測試與發布閘門通過。若僅恢復部分來源，僅釋放不依賴缺失欄位的指標。所有復歸需記錄 `recovered_at`、`replacement_batch_id`、`prior_status`、`new_status`、`qa_evidence`。

## 5. 測試必備案例（未跑不得標PASS）
- T01 正常FULL；T02 缺法人→PARTIAL且禁法人共振；T03 缺收盤價→價格相關隔離；T04 官方停牌不視為抓取故障；T05 零成交與非交易日；T06 公司行動未核對；T07 TDCC週頻未公告；T08 財報公告日前不可見；T09 單股異常其餘股票正常；T10 大批覆蓋下降阻擋族群雷達；T11 缺值不得補0；T12 重抓恢復但未PIT核准不可釋放；T13 補齊且所有Gate通過才重新納入；T14 回補不改寫歷史PIT；T15 持股異常仍出現在風險頁；T16 興櫃RAW_ONLY；T17 重複/衝突/單位；T18 官方來源失聯與速率限制。
每一測試保存輸入快照、期望/實際、原因碼、受影響指標、GitHub run、SHA256、PASS/FAIL/INCONCLUSIVE。新增來源、策略、ETL、指標公式時執行相應回歸。**既有QA-006、R7.1 Production Gate仍BLOCKED，不得以本文件或局部單元測試PASS解除。**

## 6. 系統整合契約
- 不變Raw: L0；標準化L1；核准L2。
- 資料品質決策：`scripts/jarvis_daily_quality_policy.py` 是**可獨立測試的參考決策函式**，未接入現有批次流程，不代表DAILY已部署。
- 依賴圖/整批覆蓋基線/官方交易狀態/復歸自動化與DAILY報表：待下一階段串接及E2E驗收。
- C1既有 `scripts/jarvis_analysis_scope.py` 身分/興櫃/停牌門檻優先，不得繞過。
- 本政策是**後續所有資料抓取與品質測試的驗收基準**；若實作與本規則衝突，標記FAIL/HOLD並提出版本化變更，不能靜默修改門檻。


## 2026-10-14 參考實作輸入防護修正 1.0.1

`POLICY_VERSION=C1-DAILY-DQ-1.0.1-20261014` 僅加強輸入防護，不改變本SOP的發布與回補門檻；仍未接入正式DAILY/E2E。
- 空的required_features不能證明必要特徵齊備：回傳QUARANTINE/EMPTY_REQUIRED_FEATURES，不能FULL。
- required_features必須是非空mapping，欄名為string且證據為bool；無效輸入隔離，不讓單列錯誤中斷整批。
- PASS_WITH_WARNINGS白名單必須是tuple/list/set/frozenset且每項為string；None、單一字串或非string項隔離。
- 原13項回歸加3項防護案例；完整18類SOP/E2E驗收仍待完成。測試證據見DAILY-REAL-006，不把單元測試等同管線部署。
- v1.0原行為及三個失敗反例保留；L0不覆寫，1.0.1重播寫入新quality版本。


## 2026-10-14 過程複核：參考實作 1.0.2

`POLICY_VERSION=C1-DAILY-DQ-1.0.2-20261014` 不變更發布或回補門檻。新增QA標籤型別檢查：非字串QA（如list/dict）回QUARANTINE/UNKNOWN_QA，不能因集合查找拋錯中斷批次。PASS模式不依賴警告白名單，未使用的None白名單不再引發TypeError；PASS_WITH_WARNINGS仍嚴格檢查白名單，絕不升FULL。原16項加2項參考單元回歸，與本SOP的18類端到端案例是不同集合；完整SOP/E2E未驗收、Production仍BLOCKED。1.0.1的三個失敗輸入快照與1.0.2修正證據見DAILY-REAL-007。

