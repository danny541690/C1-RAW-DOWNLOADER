# JARVIS C1 v0.95 — R12 官方規則與錯誤履歷、2026/09–11 三層深度對帳、全量放行決策

日期 2026-11-07。唯一來源庫 `danny541690/C1-RAW-DOWNLOADER`，最新 v0.95 R11 規格為主。**本輪已真正執行新版 R12 多輪 GitHub Actions，而不只是列出方案。**
重點：**暫不可直接放行 2000–2026 全量下載**。零列正式 Manifest／Checkpoint 和全部待簽資料集 contract 是正式生產控制的具體 P0 原因。正確的 Bronze 可分批先放行，但必須先完成一個 T2 真實來源下載→Drive SHA 讀回→CAS 提交成功的證據。

## 1. 新 R12 現場 Run 紀錄
- 首次 [Run 42370798355](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42370798355) failed：`NameError: FOLDER`，是試跑程式中資料夾類型常數未統一；已固定改用 `FOLDER_MIME`。
- [Run 42370877195](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42370877195) completed/success：17 個 v0.95 T1/R11/R12 單元測試通過、Drive 真實有界深層 metadata 551 物件（271 Bronze，143 Silver，63 Gold，74 Staging），來源下載 0、Drive 寫入 0、分母 UNKNOWN、T2 正式寫入仍阻擋。
- [Run 42371080573](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42371080573) completed/success：加入真實四張 Governance CSV 表狀態檢驗。
- [Run 42371261762](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42371261762) completed/success：實際 metadata 衍生 **551 筆 candidate Manifest** 和 **12 筆 issue queue**；並不是將候選提升為已驗證正式 Manifest。此輪候選範圍 SHA 及資料集官方分母仍未知。后續安全版 Artifact 使用匿名 Drive ID。
- 新 [R12 Workflow](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/main/.github/workflows/v095-r12-sep-nov-deep-manifest-retirement-preflight.yml) `workflow_dispatch`＋限定 paths push，用 9 個真實 Drive roots 限深檢查、R11 8 項測試、T1 3 項、R12 6 項、治理 3 項；**沒有新增無限制全史下載 cron**。
- R6／R7 原有定時規則尚在，不誤把巡檢結果當正式下載。

## 2. 最大的新證據：主分支四張正式治理表不是完成中的生產帳
| 正式 v0.95 管理表 | 目前真實列數 | 風險 |
|---|---:|---|
| `governance/v095/MANIFEST_INDEX.csv` | **0** | 只有表頭，不能以此決定已驗證 SHA 或正式簽入路徑 |
| `governance/v095/CHECKPOINTS.csv` | **0** | 只有表頭，無法從此證明 Crash Recovery 或 single-committer |
| `governance/v095/SOURCE_REGISTRY.csv` | **8** | **8/8 均 PENDING** |
| `governance/v095/DATASET_CONTRACTS.csv` | **39** | **39/39 均 CANDIDATE_NEEDS_SCHEMA_AND_PIT_VALIDATION** |
| 正式通過的來源資料集 contract | **0** | 尚無已核實的 source×dataset×date 正式 READY |
此項僅描述 repo 中的**生產治理 CSV**；歷史 Run／Google Drive 仍有其他來源檔和候選收據，不能擴張為「所有歷史資料都沒有」。
**不要人工填滿假 SHA／假 COMMITTED 列**。下一步須從真實 Drive 物件ID＋原始 SHA／官方契約核實候選、經 T2 原子提交後才寫入正式治理表。

## 3. 12 類缺失的根因、正式修法、當前完成度
| ID | 錯誤根因 | 現已更正或發現 | 尚需小量實測的PASS證據 |
|---|---|---|---|
| P0-01 排程混淆 | 16個 INGEST 類別與14個 BSG QA 類別混用 | R11/R12 規格拆分、靜態測試PASS | 正式 Controller 同 key 不重複認領 |
| P0-02 CAS 競寫 | Google Drive file exists 不是跨Runner交易 | 核實正式 CHECKPOINTS **0 列**，不可宣稱完成 | 兩Runner同 key 只有一個CAS COMMITTED、stale fence拒寫 |
| P0-03 Manifest分散 | R10把某些 Staging/Silver/Gold 正確候選當成沒有月夾 | R12有界深度真實 551 個 metadata、初始 candidate_manifest.csv，標示未驗證 | 真實原件 SHA、dataset identity、版本對帳及進一步限定深層路徑 |
| P0-04 官方分母 | 來源月夾有檔11/18不代表資料完整率 | 修正 UNKNOWN 不等於0/100；Drive list 檢查 `incompleteSearch`、nextPageToken | 各 dataset×官方應到日×當時上市／櫃名冊適用分母 |
| P0-05 PIT修訂 | 財報／景氣數值被更正後可能偷看未來 | 已定義首次公布、available_at、修訂版；Gold fail-closed | 官方發布原始證據與回測as-of選版 |
| P0-06 真實Adapter | R6/R7是巡檢，R10/R12是 QA，不是真正 RAW source downloader | 正式 DATASET_CONTRACTS **39/39待驗**；禁止就緒假象 | 1筆官方應到且真正缺件的v0.95 Bronze T2真實寫入 |
| P1-07 443 formula | 目錄ID/來源對應不等於公式DAG | 缺公式一律 `DISABLED_WITH_REASON` | 每個發布指標formula SHA、暖機與依賴 |
| P1-08 雙向血緣 | SHA候選對應不等於所有Rows trace | parent SHA契約定義 | T3真實 Bronze→Silver→Gold SHA反查+正向 invalidation |
| P1-09 重複QA | 同SHA既有驗收反覆掃、重下載 | 12既有scoped receipts可依SHA跳過、R12不下載來源 | 上游sha不變不重算，下游SHA變更才派 affected task |
| P1-10 Parquet小檔和不可重現 | Silver輸出帶runtime資料造成immutable collision | 十月 V2 分離內容 SHA 與版本 | 同資料、同code 兩次產生完全相同 SHA，QA後compact |
| P1-11 來源語意誤判 | TPEx 412價格缺值和TDCC股權比例警告不是HTTP失敗 | 保留原始字串和**496**集保例外群組，修尾端空白 | 官方證券種類／週別分母逐群釐清，不可強制補零 |
| P2-12 SLO與備援 | workflow綠燈不等於吞吐及還原OK | R12有真實Run、唯讀掃描量與零重抓數；仍無恢復證據 | 真正T2讀寫耗時、Drive配額、Crash Restore SHA |

## 4. 官方文獻導出的新增安全規則
1. Google Drive `files.list`：必須跟完 `nextPageToken`，遇 `incompleteSearch=true` 不可標示來源資料查無；`MD5` metadata **不能直接冒充原始SHA256**。官方：https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list 。
2. Google Drive `files.create` 上傳：官方支援部分檔案格式以**預先產生的ID**對逾時安全重試；成功後重送得到409，不會產生新副本。這是上傳去重的輔助，不等於取代交易型CAS或租約。官方：https://developers.google.com/workspace/drive/api/guides/manage-uploads 。
3. GitHub public repo 的 Workflow Artifact 可供具有repo讀取權限者取得。**原先 R12 執行物曾包含實際Drive物件ID／檔名。** 新版將公開Artifacts改為匿名化ID與統計，未來保留期縮短；**已產出的舊Artifacts尚未因程式改版被刪除**，需管理者另外刪除。官方：https://docs.github.com/en/rest/actions/artifacts 。
4. TPEx 現行 bulk 行情自 2003-08；2000～2003舊格式來源另查，不視為所有市場歷史不存在；TDCC股權分散官方資料集自2008-07建置，比例以集保庫存分母，不能誤把前期資料與比例警示當抓取失敗。

## 5. R12 後的安全調度
| 執行階段 | GitHub入口 | 運行方式 | 放行條件 |
|---|---|---|---|
| T0 12項規格及故障注入 | `v095-r11-architecture-improvement-pilot-gate.yml` | 修改或手動 | PASS，已完成 |
| T1 有界深層Manifest＋漏洞總帳 | `v095-r12-sep-nov-deep-manifest-retirement-preflight.yml` | 修改或手動，無定時狂掃 | 真實metadata、疑義清冊、不能推論完成率 |
| T2 1筆正式缺件RAW寫入 | 尚無生產定時觸發 | 僅來源已簽約且T2CAS準備好人工啟動 | HTTP原始bytes、內容SHA、Drive readback＋fenced CAS＋重跑SKIP |
| T3 1筆Silver+1個Gold | 手動放行 | T2上游已PASS | 型別＋公式/PIT＋正反向血緣 |
| T4 6筆 Bronze canary | 手動放行 | 上游階段PASS才啟動 | 6/6明確通過或隔離、單寫者、日誌及restore proof |
| 2000～2026 正式全史 | v0.95 16類邏輯槽 | **目前未核准** | T2/T4、dataset×date READY + durable lifecycle不變式通過 |

## 6. 不變的停止條件與安全旗標
`BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`、`last_evidence_verified=false`。R12 測試中的 raw download = 0、Drive data mutation = 0。**嚴禁以「程式Run SUCCESS」標成2000–2026完成；新增T2正式writer與23～27年完整度未驗證。**

## 7. 2026-11-07 R12.1 更新｜例行排程及 Google Drive 履歷自動落地
- 已在 `.github/workflows/v095-r12-sep-nov-deep-manifest-retirement-preflight.yml` 新增 `schedule: 23 18 * * 0`：每週日 UTC 18:23（台灣週一 02:23）。保留 `workflow_dispatch`／指定程式 push 觸發，僅週檢一次，不與 R6 30 分鐘、R7 2 小時的輕量清冊掃描混為新的全史抓取任務。GitHub Cron 可能延後，不能當精準交易日觸發器。
- 新增 `scripts/v095_r12_drive_audit_archive.py`：從 R12 經測試的匿名摘要 `public_report.json` 和 `r12_governance_gaps/result.json` 組出每個 Run 的決定性 JSON，寫入 v0.95 Google Drive `60_OPERATIONS_QA` 既有 Operations 資料夾。使用 Run ID＋內容 SHA 作檔名，同名則讀回重用，禁止任意覆寫；寫後取回 bytes 重新 SHA256 驗證。不把私人 Drive 檔案名稱／ID 寫進 GitHub 公開 Artifact。
- **真實執行 Run [42375085800](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42375085800) completed/success**；R11/R12 合計 **23 項**自動測試通過（7+3+2+3+8）。Drive audit `action=CREATED`、`result=PASS_DRIVE_AUDIT_BYTES_READBACK`、內容 `sha256=cf6622ee4092e7be17cc7ff23cce79e0fbfd85e99b3882f9c6358f127348fc51`，來源市場資料下載0、異動0。此證據表示週檢的**紀錄寫入**可用，不表示正式市場原件Writer/雙Runner CAS已通過。
- R12 深層掃描仍為 **551 件**（Bronze271、Silver143、Gold63、Staging74）、551 件各不重複 Drive ID；衍生 Candidate Manifest 551 列、12 筆待處理 issue queue，**不是已簽核正式 Manifest**。
- 生產治理主表 `MANIFEST_INDEX.csv=0`、`CHECKPOINTS.csv=0`；8個來源均 PENDING；39個 DATASET_CONTRACTS 均待驗證；正式下載 ready 0。保留 `BULK_COPY_APPROVED=false`、`RELEASE_APPROVED=false`。
- 資安界線：公開 GitHub Artifact 僅保留匿名 file reference＋摘要；歷史上已寫入舊 Artifact 的 Drive IDs 不會自動因程式修正刪除，需要在 GitHub 另行管理。Google Drive Operations Audit 檔案只保留不敏感狀態、問題ID、計數和RunID。
- T2 下一步：對一份已公布、確定缺失的來源原件，驗證 v0.95 原生下載 → Drive SHA讀回 → 單一正式 CAS/Checkpoint → 再執行SKIP／Stale Writer拒寫。尚未完成，**不啟動2000–2026全史下載**。
