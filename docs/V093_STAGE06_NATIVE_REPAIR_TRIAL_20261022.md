# 賈維斯 v0.93：指數與事件解析修復實測

日期：2026-10-22（Asia/Taipei）。狀態：NATIVE_PARSER_REPAIR_TRIAL_PASSED_NOT_DEPLOYED。

## 本輪完成

既有 16 筆隔離原始檔全部完成測試版解析修復，走完領取、原子不可覆寫存檔、Parquet 讀回、逐格驗證及回執結案。原始檔全部來自既有 Drive 原生封存，先逐檔核對原收據 SHA256；未向市場來源補抓或更改原始檔。正式五條排程設定與正式修復候選帳本不變。

| 資料類型 | 原始單元 | 原生紀錄 | 數值格 |
|---|---:|---:|---:|
| TPEx 指數 | 14 | 1022 | 3066 |
| TWSE 減資恢復買賣 | 1 | 2 | 10 |
| TPEx 除權息 | 1 | 17 | 289 |
| 合計 | 16 | 1041 | 3365 |

## 修正內容

- 新增獨立版本 NATIVE_INDEX_EVENT_REPAIR_V1；現行 R4 與五條 live worker 沒有改版。
- 指數以 INDEX、原生名稱與 PRICE_INDEX／TOTAL_RETURN_INDEX 保存，個股代碼留空；同名櫃買價格指數與報酬指數不混用，不杜撰官方指數代碼。
- 減資使用「恢復買賣日期」，除權息使用「除權息日期」。不以查詢月份或下載日期代替事件日期。
- 保留實際證券代碼，包括資料源中的 ETF、ETN 代碼；entity_type=SECURITY 不代表已判定為上市櫃普通股，後續分析仍須證券主檔分類。
- 金額與其他數值先保存原生欄位、字串與 Decimal 精度。本輪是原始數值逐格核對，尚未完成單位語意映射，不能視為完成億元標準化或完整財務驗證。
- 新增 LocalImmutableArtifacts：在檔案鎖內確認執行權，暫存檔 fsync 後以不可覆寫連結發布。重跑相同內容可重用，異內容拒絕覆寫；最終權威結果仍由 CAS 帳本及 fence 控制。

## 驗證與產物

本機與雲端全套各 348 項全部通過，較前輪新增 23 項；第六階段測試累計 67 項。新增案例涵蓋價格／報酬指數區分、事件日期、ETF 代碼與精度、錯誤資料集／市場／範圍、欄寬與格式、原生日期衝突、缺值不補零、來源失敗回應、輸出數值／身分／欄位遭竄改、偽造核定旗標、四份真實封存樣本的完整接點重放，以及兩個不可覆寫後端並行。

完整 16 單元在隔離 TEST_ONLY 帳本中完成：16 個新修正版任務 DONE；16 個原候選任務因同缺口測試解決而 CANCELLED_SUPERSEDED。這些狀態僅適用隔離測試副本，正式候選帳本仍保留 16 個待核定任務。

輸出封存含 16 個 Parquet、16 個驗證 JSON、不可覆寫產物、測試帳本、RESULT.json 與檔案雜湊清單。Drive 上傳後重新下載驗證 ZIP SHA256 及清單中 67 個檔案，全部通過。

- ZIP SHA256：ead64a20efce4c47f73555604bc57e6775ee022dbe0de52c637b7630c5887ccf
- 原始資料封存保持不變，市場來源 HTTP 下載 0。
- 產物：https://drive.google.com/file/d/1nD7rE2kQYBDoWA7CkZ0OQRPC9Bzk81br/view
- 程式提交：dad93ab94578e18d425884e7fedbe935b47d6e50
- 雲端驗收：https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/39715227178

## 適用範圍與下一個中斷點

本輪核對的是原生單元內的資料完整重現。兩份事件封存的資料範圍只到 2026-10-15，不代表整個十月完整；沒有因此認定後半月缺漏或重抓。numeric_semantics_verified=false、pit_verified=false、production_data_approved=false，不能視為全市場或歷史全期間驗收通過。

下一步是把這個版本及 INDEX／SECURITY、價格／報酬指數、事件日期的新輸出契約接入正式 owner 讀寫後端，驗證 Drive 發布與現有租約／CAS 的配合，再接入 RAW 補抓及完整預期單元清單。第六條 enabled=false，owner_runtime_integrated=false；五條現有工作、預算、下載規則及游標均未變更。
