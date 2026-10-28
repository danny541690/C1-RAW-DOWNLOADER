# 興櫃日期證據與合併驗收分流（2026-10-28）

## 結果

本輪修正「用一般 OHLC 規則判定興櫃 open」的驗收適用性。原件不改值。官方 2026 年 8、9 月共 12 個逐股月報 JSON 均保留 SHA、URL、日期、代碼及原始表格。

- 原 44 個疑點鍵皆有當日興櫃市場證據；最高、最低、成交股數、成交金額 176 個欄位對一致（前輪）。
- 本輪接入實際批次，六檔整個 9 月共 120 列的同四欄共 480 個欄位對一致；六個檔案由一般 OHLC 阻擋改列 ESB_RAW_ONLY_RULES_OPEN，保留原件、禁止正式分析放行。
- 44 筆 open：40 筆與前一筆官方日均價相等；其餘 4 筆前一筆均價為零，與更早最近非零均價相等。這是觀察結果，沒有核准 forward-fill 規則，也未認證完整交易日曆。
- close 僅檢查當日高低範圍，尚未取得官方末筆成交價獨立比對；不能聲稱開高低收全數驗畢。
- 完整程式回歸 846 項通過（含新增 13 項），無失敗。這不代表八組真實資料驗收全部通過。

## 批次清單

337281 是凍結單元與補存版本混合清單筆數，不是核准母體、唯一資料總數或完整性分母。562 筆有部分內容證據，其中 556 REMAINING_RULES_OPEN、6 ESB_RAW_ONLY_RULES_OPEN。CONTENT_BLOCKED 由 12 降為 6，剩餘是早期財報；99390 RAW_NOT_IN_LOCAL_CACHE 只表示本機未讀回，237323 RECONCILE_FROZEN_MISSING 仍需核對最新遠端收據，不能直接當成待重新下載數。

八組整組狀態仍為 0 完成、6 部分、1 未確認、1 阻擋；核准正式分析／回測範圍 0。批次 summary 中 groups 為原執行器保守狀態，未自動匯入外部跨來源、復原等證據；整組現況依本報告及既有進度表。

## 實作與保護

--esb-evidence 指向含 manifest.json 與官方原件的目錄。必須驗原件 SHA、官方 URL／查詢代碼月份、內文月份、標題、公司代碼、欄位及逐日日期。只有證明的鍵才分流，不因目前市場別或股票代碼白名單放寬。

逐列重比高低、量額；來源值不合、日別缺證、系統外成交契約未核、close 超高低仍阻擋。證據變動納入 checkpoint signature，不能沿用舊快取。本批不寫正式資料庫，不關閉品質任務、不改 RAW、不核准興櫃進入正式回測。

## 再執行

在專案根目錄：

```bash
python -m scripts.v093_prelaunch_acceptance_batch --register /path/to/register --raw-cache /path/to/raw-cache --out /path/to/output --esb-evidence /path/to/esb-evidence --resume /path/to/output/checkpoint.json
```

必須提供原先 register 與 RAW cache；本證據包不複製完整來源資料庫。官方歷史資料的本次抓取時間不等於歷史公告可得時間，PIT 仍未驗證。
