# 賈維斯七大來源：37條驗收進度與修補／發布門檻（V2）

更新：2026-10-28T06:53:29.525259+08:00。程式碼核對版本：`2a00959720b1c2d7968e616322855308be5e6dc9`。

本版是37條規則的靜態實作對照與待辦表，不是一次新的全量資料驗收。保留2026-10-27 V1歷史規格；本版不改寫原始驗收結果。

## 是否要37條全過才能修補？

不必。修補、驗收、發布是三個不同門檻。既有已驗證路由可以繼續有界修補；新路由先對實際小範圍驗證，再擴大。修補輸出保留原件並進待驗區，未通過適用規則不得提供正式用途。

|階段|允許條件|產出與限制|
|---|---|---|
|修補執行|該路由必要的原件保留、期別定位、錯誤分類、重試限額、讀回與寫入保護已驗證|可取得／重解析原件；不可自動關閉數據品質缺口|
|正式分析|該來源×資料集×期間×欄位的適用規則通過；用途不依賴尚未驗證的PIT|只開放證據綁定範圍；有待確認關鍵項目則限制用途|
|歷史回測|上述條件及當時可得時間、版本、歷史母體與價格調整依賴全部通過|PIT未知或母體未核准時不得作為正式歷史回測輸入|
|整庫100%聲明|核准完整分母、逐適用單元驗收、全部缺口與未知處理完成|目前尚無此證據；不得用805個軟體案例代表整庫驗收|

37條依來源與資料集適用；不適用必須有理由和證據。UNKNOWN不能當PASS。跨來源共同依賴失敗時，相關發布範圍同樣被阻擋。

## 本輪確認與限制

- 規則定義37/37存在。以下每條都有來源、實作線索、待完成項目與必要證據。
- 程式碼存在只標「部分實作線索」，不授予該規則完整測試通過。未找到足夠映射標「本輪未建立證據」，不斷言完全沒實作。
- 發布閘門要求sha_readback、schema、unit、unique_key、numeric、universe、pit、source_contract、dependency；仍需實際範圍證據。
- 本輪新下載0、新RAW驗證0、任務關閉0、核准發布範圍0；尚未完成合併式真實資料驗收。
- 既有805案例是先前軟體回歸結果，本輪未重跑，也未算成37條或全量真實資料PASS。

## 37條逐項進度

|ID|面向／來源|實作核對|真實資料全範圍驗收|尚需完成|
|---|---|---|---|---|
|G01|應有母體／全部|本輪未建立證據|UNKNOWN|核准逐來源、資料集、期間的應有歷史母體及分母；候選清單不可直接核准|
|G02|口徑與覆蓋／全部|[v093_layer02_governance.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_layer02_governance.py)|UNKNOWN|逐資料集核對頻率、單元與覆蓋範圍，消除檔案數和觀察值數混算|
|G03|原件存取／全部|[v093_official_repair.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_repair.py)、[v093_release_publisher.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_release_publisher.py)|UNKNOWN|對實際待發布原件逐檔遠端讀回驗SHA；不能用舊抽查替代全集|
|G04|回應內容／全部|[v093_official_finmind_gapfill.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_finmind_gapfill.py)、[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|將HTTP成功、內容成功、空回應、拒絕與真無資料逐單元區分|
|G05|壓縮與文件／全部|[v093_taifex_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_taifex_independent.py)、[v093_ndc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_ndc_independent.py)|UNKNOWN|逐實際包核CRC、全部成員、解壓限制、頁數及截斷|
|G06|日期語意／全部|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)、[v093_standard_r4.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_standard_r4.py)|UNKNOWN|逐單元核內容期別；報表期別、匯出日、公告日及交易日分開|
|G07|證券與主鍵／全部|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|補前導零等未覆蓋代碼規則與實際全範圍主鍵證據|
|G08|完整性／全部|[v093_layer02_governance.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_layer02_governance.py)|UNKNOWN|待核准母體後計算expected/actual/missing，不將UNKNOWN當完整|
|G09|空值與不適用／全部|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|核定每資料集空值及不適用理由，來源空回應不可逕認無資料|
|G10|數值與單位／全部|[v093_source_pit_unit_evidence.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_source_pit_unit_evidence.py)|UNKNOWN|建立逐欄原生單位、幣別、倍率與精度契約；metadata探針不等於數值驗收|
|G11|欄位關係／全部|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|補齊適用的逐欄公式、容差與真實數據結果|
|G12|檢查覆蓋／全部|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|將37規則映射到每個待發布單元；列出未檢欄位與略過原因|
|G13|PIT與版本／全部|[v093_source_pit_unit_evidence.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_source_pit_unit_evidence.py)、[v093_layer02_governance.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_layer02_governance.py)|UNKNOWN|取得當時可得時間與歷史版本證據；尚無PIT證據的歷史回測不得放行|
|G14|跨來源一致／全部|[v093_cross_source_numeric_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_cross_source_numeric_audit.py)|UNKNOWN|先核單位、還原與共同上游，再取得獨立逐值比較證據；比較器刻意不授予認證|
|G15|重複與修訂／全部|[v093_official_repair.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_repair.py)|UNKNOWN|補跨來源、重疊包、修訂版本與語意主鍵去重證據|
|G16|排程與競態／全部|[v093_repair_coordination.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_repair_coordination.py)|UNKNOWN|將租約、競態與斷點恢復證據映射到各實際worker；勿宣稱所有來源已驗完|
|G17|重試與路由／全部|[v093_official_finmind_gapfill.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_finmind_gapfill.py)、[v093_official_repair.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_repair.py)|UNKNOWN|沿用累計次數、冷卻與來源配額；達上限或路由未明列待處理，不重設強跑|
|G18|驗收與關閉／全部|[v093_release_publisher.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_release_publisher.py)|UNKNOWN|發布器讀取證據並核SHA，但全37規則與逐任務VERIFIED/CLOSED整合尚未證明完成|
|G19|歷程與重開／全部|本輪未建立證據|UNKNOWN|驗證追加歷程、重開及依賴重驗的全流程證據；本輪不假定既有帳本已完整達標|
|G20|多處保存／全部|本輪未建立證據|UNKNOWN|本版報告三處保存不代表原始資料庫全量備份或復原演練通過|
|G21|期限與鮮度／全部|[v093_ndc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_ndc_independent.py)|UNKNOWN|重新查證到期與來源最新發布；舊未發布狀態須重驗|
|G22|需求外資料／全部|本輪未建立證據|UNKNOWN|另列需求、指標與來源映射；七來源不能代表所有功能已覆蓋|
|T01|日行情／TWSE；TPEx|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|全適用歷史證券逐日檢查價格、量值與交易狀態；未覆蓋代碼不可略過|
|T02|籌碼與事件／TWSE；TPEx|[v093_official_content_audit.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_content_audit.py)|UNKNOWN|融資券已有部分解析；法人、事件與其他表仍需逐資料集契約和真值驗收|
|T03|證券歷史／TWSE；TPEx|本輪未建立證據|UNKNOWN|補歷史證券主檔、轉市場、下市及公司行動；防倖存者偏差與還原混用|
|M01|財報母體／MOPS|[v093_official_repair.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_repair.py)、[v093_standard_r4.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_standard_r4.py)|UNKNOWN|核准歷史公司/季別/產業報表母體；早期比較路由保留未解，非直接認無資料|
|M02|財報數值／MOPS|[v093_standard_r4.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_standard_r4.py)|UNKNOWN|解析有財報值不等於三表勾稽通過；補幣別、單季累計、科目與公式驗證|
|M03|營收與發布／MOPS|[v093_source_pit_unit_evidence.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_source_pit_unit_evidence.py)|UNKNOWN|補實際公告與修訂證據；匯出日期不得替代公告時間|
|F01|資料集權限／FinMind|[v093_official_finmind_gapfill.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_finmind_gapfill.py)|UNKNOWN|逐資料集檢查授權與完整頁數；目前空回應及配額保護只覆蓋部分規則|
|F02|補件與語意／FinMind|[v093_official_finmind_gapfill.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_official_finmind_gapfill.py)|UNKNOWN|補件仍保留官方缺口；補逐日逐欄語意、單位、PIT與母體驗證|
|A01|期貨主鍵／TAIFEX|[v093_taifex_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_taifex_independent.py)|UNKNOWN|補全部商品、合約、盤別、履約價與期權類型的主鍵覆蓋及夜盤語意|
|A02|期貨包完整／TAIFEX|[v093_taifex_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_taifex_independent.py)|UNKNOWN|核對catalog與實際成員；雙向狀態分類差異待對帳，年度包不重算12月|
|A03|期貨數值／TAIFEX|[v093_taifex_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_taifex_independent.py)|UNKNOWN|基本CSV/數值檢查不足；補分商品單位、結算/收盤、OI及特殊價差規則|
|D01|集保日期母體／TDCC|[v093_tdcc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_tdcc_independent.py)|UNKNOWN|查詢選單與4100候選不等於歷史母體；早期查詢未提供另找官方檔案|
|D02|集保級距／TDCC|[v093_tdcc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_tdcc_independent.py)|UNKNOWN|整數與列數檢查只是部分實作；補級距全集、單位、合計與容差|
|N01|景氣序列／NDC|[v093_ndc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_ndc_independent.py)|UNKNOWN|逐序列核頻率、基期、季調、單位及應有期別；月包數不等於全序列完整|
|N02|景氣版本發布／NDC|[v093_ndc_independent.py](https://github.com/danny541690/C1-RAW-DOWNLOADER/blob/2a00959720b1c2d7968e616322855308be5e6dc9/scripts/v093_ndc_independent.py)|UNKNOWN|來源檔版本不等於歷史發布vintage；補當時可得版本與最新發布重查|

## 合併式實資料驗收的下一批工作

1. 對帳凍結盤點與目前收據，先列出各來源實際持有的原件與未解任務；不把10/27快照缺口直接當今天缺口。
2. 以來源×資料集×年月×代碼／合約建立範圍和適用規則；先核母體與欄位契約，保留待確認分母。
3. 對同一原件合併執行讀回SHA、CRC／成員、schema、期別、主鍵、欄位數值與檢查覆蓋，避免重複下載。
4. 補齊歷史母體、單位、獨立比對與PIT／修訂版本證據；只比較數字相同不足以核准。
5. 逐單元輸出PASS／FAIL／UNKNOWN／有證據的NOT_APPLICABLE，形成可用、隔離、補下載、待確認清單；只核准全部適用規則通過的範圍。
6. 保留task_id、來源／資料集、年月、原件SHA、驗收artifact SHA、規則版本、修補前後狀態、run URL與時間；失敗回到既有有界修補隊列，不重設上限。

## 稽核資料

同包的`acceptance_progress.json`保留全部37條的原規格通過條件、必要證據、逐條實作連結與核對檔案SHA256，供後續自動化接續。此JSON仍屬進度登錄，未接上排程驗收器。

報告保存不代表原始資料庫備份完成。GitHub、Drive與ChatGPT保存的是此版報告包，原件復原演練仍需另驗。
