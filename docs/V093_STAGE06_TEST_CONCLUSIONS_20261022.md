## 2026-10-22 20:07 Taipei：自動第二輪實測確認

同一 GitHub run 39774302659 在 WAITING_RECHECK 後，自動重新從 2026-10 掃描；2026-10-22T12:07:35.481226+00:00 狀態 SCANNING，last_scanned_month=2026-10、next_month=2026-09、cycles_completed_this_run=1。已確認沒有停在 2000-01。這是重查啟動證據，不代表所有資料完整；coverage_certified=false，RAW 補抓綁定仍未完成。

# 連續模式已實際完成掃描並等待下一輪（2026-10-22 台北20:03）

正式新版run39774302659已在20:02:22保存：continuous=true、phase=WAITING_RECHECK、cycles_completed_this_run=1、last_scanned_month=2000-01、next_month=2026-10、recheck_seconds=300。這次不是掃完後結束workflow；同一producer job仍in_progress、持有自己的有效鎖，預定約20:07重新載入上游再從最新月開始。第二循環尚待觀察。

財報2026-03於20:03已163/215 RESOLVED、52待處理。一次性run39773976279成功結束：25項完成、0失敗、1次CAS競爭延後，status=DEFERRED_CAS_CONTENTION，未將延後任務當DONE。原FINANCIAL鎖已釋放，由新run39774302659的financial-repairs job接手；正式任務仍保存，不需重抓或重設。

使用者另問聊天斷線是否伺服器擁擠：剛查OpenAI官方status.openai.com顯示fully operational、未公告系統問題；這不能排除個別客戶端／工具連線問題，也不能確認此次聊天斷線根因。本輪已證實的GitHub CAS競爭屬帳本併發，不是OpenAI伺服器擁擠證據。聊天重接期間GitHub進度仍由2013-09前進到2000-01，且新財報修復有增加。

---

# 新版第六條已正式接手並持續掃描（2026-10-22 台北20:01）

先前等待交接已解除。舊run39772255253於19:59因CAS_RETRY_EXHAUSTED失敗，持久鎖已正常釋放，保留2014-03待接續位置。新版run39774302659的producer job119809267636已取得RECONCILE owner39774302659/RECONCILE、fence10；雲端完整回歸與額度檢查步驟均成功，此版本本機463項全部通過。正式控制帳本已讀回continuous=true、phase=SCANNING、recheck_seconds=300、last_scanned_month=2013-09、next_month=2013-08、updated_utc=2026-10-22T12:01:06.718660+00:00，確認不是仍在排隊或只完成測試。

部署提交632c389009d4a2856af22e12baffac32e792e730。新run：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39774302659 。新版在原60分鐘預算內完成掃描後，保存WAITING_RECHECK與下一輪2026-10，等待5分鐘、重載上游索引再掃；仍受額度與鎖／期限限制。尚未實際觀察完整第二循環，不能將此項寫成真實第二輪已通過；本機兩輪、慢速owner檢查、預算與鎖邊界已有測試。

財報補修run39773976279仍在執行，2026-03於20:01已161/215 RESOLVED、54待處理；2026-06已213/213。新版同輪FINANCIAL修復job119809267381在原FINANCIAL concurrency排隊，原owner未被取代；先前run39772732264的FINANCIAL工作實際完成22項、0失敗，pending producer被新版取代而取消，不是資料回滾。

下一接續：讀正式control與兩run終態；確認掃到2000-01後phase／next_month及下一循環，並核對財報餘54項。不要重啟已在工作的owner或重設原始下載游標／次數／已完成任務。RAW補抓transport、額外來源、其他adapter、全部完整性及PIT仍未接通或未全面通過。

---

# 連續重查接手續跑（2026-10-22 台北19:58暫存）
使用者要求從斷點接續。最新部署632c389009d4a2856af22e12baffac32e792e730，新增慢速owner檢查超過輪詢間隔與剩餘預算的兩項邊界測試，避免負數sleep或逾時後開始新循環。本機463項通過；上一版雲端461項及隔離CAS測試已通過，最新雲端producer尚待原批次結束後進行回歸和運作，勿提前稱463雲端已通過。
最新正式run39774302659（producer＋原FINANCIAL owner修復job）：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39774302659 。19:57兩job皆pending；producer等39772255253原RECONCILE槽，FINANCIAL等既有財報批次。先前39772732264的pending producer被最新排隊工作取代而cancelled，已成功完成的22筆財報修復仍保留；這不代表資料回滾。
另以現有一次性財報工作流程啟動39773976279，限定2026-03、最多20分鐘，與常態FINANCIAL同一concurrency／持久pool。提交28a2a73667c31a733531a8359f7c94016e0066d8。19:57觀察2026-03已146/215 RESOLVED；2026-06已213/213。不是新增第七條cron，也未停止其他四線。
本機執行環境重建曾缺google／pyarrow套件，本輪已在 /workspace/scratch/ac6f1be9a8a8/jarvis-test-env 建立測試venv並安裝requirements-qa.lock，再完整跑463項通過。依賴缺失那次216項測試執行失敗不能算驗收通過；當時候選提交未發布。使用venv的python續做，不假定使用者目錄的套件在環境重建後仍存在。
當前斷點：等待39772255253結束並確認39774302659的producer取得RECONCILE槽，讀control.continuous=true／phase／next_month；完成後讀回至少一次新版正式掃描進度。原始碼及測試已部署，連續第二輪實跑仍待確認。未完成RAW補抓綁定、其他來源、全部資料完整性／PIT的限制保持。
---

# 第六條連續重查修正已部署（2026-10-22 台北19:45）

使用者要求第六條不要掃到2000-01後停止等整點，並要求更新六條進度。已查明舊版每次只跑一輪，結束後等待下一次cron；不是永久停用。已部署3345b6885bc7387724742f0a002c4432de7ae7cb，新版在60分鐘預算內掃完後等待5分鐘，再重新取得上游索引、從2026-10往2000-01重查。控制帳本增加SCANNING／SWEEP_COMPLETE／WAITING_RECHECK與next_month；空月份UNKNOWN仍保留，資料沒變不重寫INPUTS清單。

第六條workflow的concurrency改為各job獨立：producer使用原jarvis-v093-live-reconcile-repair，FINANCIAL修復job使用原jarvis-v093-live-financial、最多6分鐘，避免延誤一般財報轉換；沒有增加第七條cron。PRICE仍由自己的owner消費。RAW補抓transport與新來源仍未接通，禁止宣稱全類型修復完成。

本機461項全部通過；兩個雲端461項回歸亦通過：39772732231（真實Drive step在push略過）及39772732275（隔離雲端CAS canary PASS）。本輪新增11項，驗證循環回最新、重新載入上游、部分斷點續跑、時間／額度停止、定期檢查owner、CAS退避與保存任務。CAS競爭加入有界隨機退避，修復回執衝突保留claim／候選檔並延後，不假設DONE。

正式新run39772732264：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39772732264 。19:44觀察financial-repairs job119804021091已執行；producer job119804021327等待原run39772255253完成後自動取得原槽。尚未觀察新版producer進入連續第二輪，不可宣稱這部分正式實跑已完成。舊producer19:44仍在2025-02，新修復2026-03由114增到115/215；2026-06已213/213全修復。

當時其他最新目錄：RAW2013-01、QA12017-09、PRICE2020-05、FINANCIAL2018-02、CHIP2021-08；仍需依MONTH_STATE和STATUS確認實際單元，不能僅憑目錄創建當完整資料。原始日資料最近權威收據仍確認至2026-10-21。

下一個接續點：先確認39772255253終態及新producer119804021327開始；查control.continuous／phase／next_month，驗證掃到2000-01後5分鐘重啟、上游索引重新取得；同時查FINANCIAL owner回執。不重設RAW／QA游標、下載計次或已完成修復，不停止其他正在跑的排程。


---

# 賈維斯0.93：中斷續跑與測試結論（2026-10-22）
更新：台北17:37。後續請以正式收據與執行紀錄為準。

## 本次接續
- RAW、QA1、PRICE、CHIP的原執行工作仍在運作，保留其斷點與原始檔。
- 既有財報工作槽空閒時，啟動既有一次性工作流程的60分鐘修復批次；沒有增加第七條週期排程。
- run39756682132：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39756682132
- 提交71f1fcebaa3ce24eeba78ab5421a21cd212ecb08；使用原jarvis-v093-live-financial concurrency與FINANCIAL持久pool，沒有取消其他工作或借用其鎖。
- 75分鐘工作流程期限、90分鐘持久鎖；啟動前預算檢查最多5分鐘，修復工作最多60分鐘。原五線常態60分鐘設定不變；本次屬有界修復續跑。
- 雲端完整回歸步驟與額度檢查均成功，正式修復步驟已運作。
- 本次續跑前2026-06已修復120/213；17:37讀回為122/213，仍有91待處理，其中1已領取。其他待修月份包括2026-03的215項、2025-12的209項。此為快照，不代表最終批次結果。

## 測試結論
| 項目 | 結論 | 實證及限制 |
|---|---|---|
| 完整回歸 | 450項本機與雲端既有驗證通過；本次雲端回歸步驟亦成功 | 例行程式與帳本測試通過，不代表歷史所有資料通過 |
| 缺口帳本與任務 | 已實作並驗證 | 去重、CAS、owner路由、鎖與fence、保留未知結果、版本接手 |
| 原生價格／事件修復 | 真實樣本通過 | 16檔、1041原生紀錄、3365數值格；支援範圍限已核准adapter |
| MOPS三大財報修復 | 真實樣本通過並已正式運作 | 14檔、13276數值格；保留原生單位、缺值、YTD與INSTANT，公告時間不推測 |
| Drive＋GitHub發布 | 真實整合實證通過 | 4份樣本737格；不可覆寫、讀回hash、拒絕失鎖舊owner、重用已存輸出、衝突檔拒絕 |
| 實際修復 | 有正式完成收據 | 今日已結案且有完整回報批次確認至少316項：PRICE107、FINANCIAL209；含2023-03的89項全部修復。本次17:37又見2026-06增加2項，當前批次尚未結案 |
| 中斷續跑 | 已實證 | 先核對run／鎖／收據再接續；未知結果不盲目重送；外部限流仍可能中止單輪 |
| 全資料庫完整性 | 尚未通過 | all_data_repaired=false、coverage_certified=false、production_data_approved=false |

## 尚待完成
1. RAW缺漏額外補抓的正式transport、原生持久計次／意圖／回執綁定；現有測試注入transport合約不代表正式補抓已接通。
2. 完整預期單元清單、歷史上市上櫃母體、來源可得性與欄位／單位語意核對。
3. 其他資料類型的自動修復adapter與正式消費端遷移；未支援類型仍BLOCKED_APPROVAL或HOLD。
4. 財報公告PIT、數值語意及所有資料的分析發布驗收。
5. FinLab／Fugle權限與方案、TDCC adapter、Goodinfo可用正式API確認；新來源尚未啟用。
6. 10/22當日日資料尚未在本次讀取的權威RAW日資料收據中取得保存完成證明；最近已確認TWSE／TPEx日資料至2026-10-21。

## 今日數量的統計口徑
台北00:00之後啟動且已結案、具有完整正式回報的批次下限：RAW成功保存2742個單元；QA1基本通過19804；PRICE暫存5046、隔離1153；FINANCIAL暫存296、隔離1374；CHIP暫存6791。進行中與失敗批次已保存但未結案部分未納入。不同階段不可加總為原始下載量；一個單元不是一檔股票或一列資料。

## 下一接續點
先查run39756682132與正式2026-06／2026-03財報月分片，確認當前owner及回執後接續；不重設已完成89項、下載次數或RAW斷點。第六條對帳上輪已掃描到2000-01，下一輪繼續接納新的上游資料；空月份UNKNOWN，不可將掃描完成認定為缺漏全部補齊。
