import pathlib,csv,json,hashlib,zipfile
O=pathlib.Path('acceptance');ev=json.load(open(O/'review_evidence.json'));findings=[]
def add(i,status,item,count,unit,proof,action,rules):findings.append(dict(複核ID=i,證據狀態=status,問題或限制=item,數量=count,數量口徑=unit,證據=proof,處理要求=action,對應驗收規格=rules))
add('R01','既有界限再確認','完整歷史應有母體尚未核准','UNKNOWN','全庫股票×日期×欄位','基準14_應有範圍與驗收.csv','分開候選、正式計畫與適用觀察值；不可報全庫100%','G01/G02/G22')
add('R02','本輪基準全量掃描確認','Q1以外仍保留品質旗標',1145,'任務單元；可能含舊版本旗標','review_evidence.json；開放檢查非空且主要代碼非Q1','次要問題不能被退避/限流遮蔽；先比對檢查輸入SHA確認旗標仍適用','G12/G18/G19')
add('R03','本輪基準全量掃描確認','P0且補正狀態空白',45820,'任務單元；不是已證實值錯誤','P0且檢查狀態空白','先驗既有原件；P0不等於全面正確','G12/G18')
add('R04','本輪基準全量掃描確認','RAW帳本時間欄空白',187662,'任務單元，含大量未嘗試候選','raw_timestamp_absent；已下載缺捕獲時間=0','核對來源原收據；未嘗試時間空白合理，不自造捕獲時間','G06/G19')
add('R05','本輪基準全量掃描確認','檢查帳本時間欄空白',264930,'任務單元；不等於證明從未檢查','check_timestamp_absent','找既有檢查收據；未找到則待驗證，不重新下載成功原件','G12/G18/G19')
add('R06','本輪合成測試重現','混合代碼表的OHLC前導零覆蓋缺口',1,'合成反例；不是實際市場錯誤數','review_evidence.json.synthetic_parser_probe；當前official_content_audit.py','四碼非零開頭以外證券先按需求母體決定適用；適用就必須檢查、否則明列跳過','G07/G12/T01')
add('R07','本輪程式靜態複核確認','修補CLI只驗填報結構，未讀實際驗收證據',1,'追蹤工具設計缺口；不是已發生錯誤關閉事件','基準register.py record；實際repair_events為0','部署前增加獨立驗收artifact與SHA綁定；布林值不能取代實際驗收','G18')
add('R08','既有界限再確認','基本格式/內容檢查不是全欄數值與PIT驗收','UNKNOWN','全庫尚未完成此層驗收','official_content_audit.py固定pit_verified=False；財報保留未證明項','逐dataset建立欄位與PIT規則，未覆蓋者保持UNKNOWN','G10/G12/G13/M02/M03')
add('R09','既有需求缺口再確認','七來源單元清單未證明全部72國際序列及XQ需求覆蓋','UNKNOWN','需求覆蓋；不是新增下載數','基準14表：72指標/主力等範圍','建立需求→來源→欄位→可用期映射；使用者停用功能不強行啟動','G22')
with open(O/'複核發現與待確認清單.csv','w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(findings[0]));w.writeheader();w.writerows(findings)
queues=[
['Q_DOWNLOAD','可直接補下載','O7與有證據確認原件缺失的O1/O9','G01/G03/G08/G09','先核定適用性與既有成功收據；只抓缺項'],
['Q_VERIFY','先驗既有原件','Q1/O8/P0及次要品質旗標','G10/G12/G13/G18','先遠端讀原件；驗不過再決定補下載'],
['Q_CODE','需修程式／路由','Q3/O3/O4及R06/R07','G04/G05/G07/G12/G18','同錯誤群先canary驗證解法，避免全庫重抓'],
['Q_LIMIT','來源限制／等待','Q2/Q4/Q5/O2/O6/P1/P2','G17/G21','P2尚未到期；O2與P1需證據且定期重查；不能當永久完整'],
['Q_UNKNOWN','待確認／衝突','O1/O5/O9與母體/日期/版本衝突','G01/G06/G14/G15','證據不足不填0、不關閉；必要時保留不可恢復歷史缺口']]
with open(O/'五個處理佇列與分流表.csv','w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows([['佇列ID','佇列','候選問題','驗收規格','動作']]+queues)
# Preserve exact code evidence with hashes, no credentials or raw request secrets.
paths=list(pathlib.Path('review').glob('*.py'));index=[]
for p in paths:
 raw=p.read_bytes();index.append({'local_evidence_file':p.name,'repository':'danny541690/C1-RAW-DOWNLOADER','repository_path':('scripts/'+p.name[len('scripts_'):] if p.name.startswith('scripts_') else 'reports/raw-register/20261027_v1/register.py'),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob_sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
(O/'inspected_code_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
md='''# JARVIS 七大來源錯誤處理與驗收規範表

版本：JARVIS_RAW_ACCEPTANCE_20261027_V1。日期：2026-10-27（台灣）。基準：JARVIS_RAW_REGISTER_20261027_V1。

**狀態：規範已建立，尚未部署到市場下載排程。此輪未補下載市場資料、未修正原始值、未關閉任何資料缺口。**

## 複核範圍與界限

本輪重新掃描既有337023個任務單元、七來源壓縮主表、來源範圍限制與檢查紀錄；並閱讀當前七份關鍵程式（官方內容檢查、PIT單位證據、TAIFEX、TDCC、NDC、問題分類、修補追蹤CLI）。以合成資料測試一個檢查覆蓋反例。不是逐份重新下載/讀回所有遠端RAW，也不是所有實際數值逐欄重新驗證；當前錯誤數仍以盤點基準為準，不冒充即時全庫狀態。

基準337023=已下載99700+未取得合格原件237323；已下載內80488基本格式存檔通過、19212待內容驗證。品質待核28546與未下載可能重疊。TDCC含180565個候選未嘗試。全庫應有觀察值分母及完整率仍UNKNOWN。

本輪未發現已下載單元SHA格式無效或原件參照空白（各0），但這僅為主表欄位檢查，不等於實際遠端bytes、內容值與PIT均正確。

## 新增明列的檢查與證據缺口

|項目|結果|判讀|
|---|---:|---|
|主要分類非Q1但保留品質旗標|1145單元|先比對原件/檢查輸入版本；保留次要問題|
|P0且沒有補正狀態|45820單元|存檔不等於全面驗收，先驗原件|
|RAW帳本時間欄空白|187662單元|含未嘗試候選；已下載缺捕獲時間為0，不能全部判壞|
|檢查帳本時間欄空白|264930單元|找收據或重驗；不能斷言從未檢查|
|OHLC前導零代碼覆蓋|合成反例已重現|混表中2330有檢，0050異常未檢且unverified空白；不是實際市場錯誤證明|
|修補事件關閉證據|CLI只驗填報結構|需獨立驗收器讀實際證據，不能靠自填true關閉|

18700個基準單元的代碼字串以0開頭，但包含候選與不同資料集；**不能把18700當成已受OHLC漏檢影響的數量**。哪些證券型態屬於研究範圍，先核定母體，再決定必檢或明列不適用。

## 驗收層次

|層次|要驗的事|不能替代的下一層|
|---|---|---|
|L0 應有範圍|歷史證券、資料集、日期、欄位、頻率、適用性|未建計畫不能當完整|
|L1 原件取得|遠端讀回、SHA/長度、格式、壓縮CRC/頁表完整|SHA正確不代表數值正確|
|L2 語意與覆蓋|期間、公司、合約、盤別、分頁、主鍵、單位、空值|有部分資料不能認定全包齊全|
|L3 數值驗證|每個必要欄規則、數值域、表內關係、跨來源同語意差異|單一合理性公式不能證明PIT|
|L4 PIT與修訂|當時公告可得時間、修訂版本、決策時點|最新修訂值不代表當年可得|
|L5 關閉與留存|獨立驗收報告綁定任務與SHA，事件追加、可重開|關閉一項不能代表整來源100%|

每項結果採PASS、FAIL、UNKNOWN、NOT_APPLICABLE；UNKNOWN不得視為PASS。NOT_APPLICABLE必須有適用性證據、理由及核准紀錄。資料確實無法取得仍保留缺口，不以排除方式做出100%。

## 七來源主要驗收契約

|來源|主要核對|禁止的捷徑|
|---|---|---|
|TWSE|歷史證券母體、資料實際日期、OHLC/成交、籌碼、事件、價格基準|當前快照充歷史、靜默漏代碼、混還原/未還原價|
|TPEx|同上，另保留各時期表頭與單位差異、非交易狀態|把上市表的欄位/規則無條件套上櫃|
|MOPS|每組應有公司與科目、合併/個別、單季/累計、幣別、公告/更正|部分公司回應當全組完成、匯出日當公告日|
|FinMind|資料集權限、完整日期覆蓋、原生單位、調整基準、上游血緣|補件自動關閉官方缺口、同上游稱獨立驗證|
|TAIFEX|商品/到期月/盤別/交易日/履約價等主鍵、年度包與快照範圍|夜盤日期誤接、年度包乘12、後來快照冒充遺失當日|
|TDCC|實際發布週曆、當期適用證券、級距/人數/股數/比率與合計|4100候選當歷史全集、空級距補0、所有列強迫合計100%|
|NDC|逐序列頻率/期別/單位/基期/季調、發布版本與歷史vintage|存月包即全序列完整、永久沿用舊版未發布判斷|

37條逐項規格在「七大來源錯誤處理與驗收規格表.csv」及acceptance_rules.json：每條含觸發條件、方法、通過/失敗條件、處理原則、必留證據、優先序與現有證據狀態。規則是待接入自動驗收的契約，不代表所有來源已具備自動檢查器。

## 可執行的處理順序

1. 先核定母體與每資料集必要欄；未核定者保持UNKNOWN。
2. 先處理R06檢查覆蓋與R07關閉證據規則，建立正反例測試；其他已有有效方案的錯誤群可並行。
3. 優先驗既有原件：19212待內容驗證、Q1與P0；不用全部重抓。
4. 補41個缺少補正帳本月份（2007-01至2010-05）的檢查證據，RAW存在者先讀原件。
5. 分五個佇列處理：可補下載、先驗原件、需修程式、來源限制/等待、待確認。分流以證據為準，不只看Q/O代碼；次要品質旗標同時保留。
6. 按來源/錯誤群先canary，涵蓋早中晚歷史、表頭改版、假日/無交易、空白/錯誤頁、合法負值、前導零/不同型態、原件截斷、重送/競態、錯日期、修訂版與PIT不明等正反例。
7. 解法通過才批次處理受影響單元；程式成功、工作流綠燈不能直接關閉資料缺口。

來源限流尊重retry_after；認證、方案與未提供歷史分開。建議每任務每輪最多3次是**本規範待配置建議**，不覆蓋現有排程重試次數。來源發布時程、期限、數值容差須逐資料集核准，不套同一固定值。

## 數值容差與PIT細則

- RAW保留原生單位與幣別；展示金額以億元，換算與幣別另欄。外幣不未經匯率證據直接標新台幣。
- OHLC關係使用原生精度；表內財務合計容差依公布最小單位、項數與公式決定；不同定義不以放大容差掩蓋差異。
- EPS分母、銀行/保險報表、財報重編、非交易價與期貨價差須資料集專用規則。
- 只有公告日期、沒有時刻，只能依明確保守可得時點政策使用；不能宣稱公告當日盤中可得。
- 國際72序列、XQ主力等需求另建需求對照，不能用七來源下載量代替全部指標覆蓋。使用者暫停的逐分點/Top15重排名等維持停用。

## 關閉所需證據

最少：task_id、source、dataset、unit_id、content_period、raw_file_ref、raw_sha256、remote_readback_sha256、bytes、universe_version、schema_version、parser_version、validator_version、rule_results、expected/actual/missing/uncovered_keys、publication/vintage證據、validation_artifact_ref與SHA、執行連結、驗收人及帶時區時間。

VERIFIED與CLOSED必須同一原件SHA、同一任務及可追溯規則結果；必需規則全PASS，缺口/未知/衝突為0。NOT_APPLICABLE可有，但必須證據審核且不任意縮小需求。先VERIFIED再CLOSED；新問題追加REOPENED，保留原件與舊事件。不能把欄位勾選true當作真正驗收。

## 完整率與交付

完整性=驗收通過的適用觀察值/全部已核准適用應有觀察值。另分開公布取得率、欄位覆蓋、數值通過、PIT通過、未知及來源限制；每個指標揭露分母。分母未核准就UNKNOWN；以「已知缺口清零」冒充全庫100%禁止。

[盤點基準GitHub固定版本](https://github.com/danny541690/C1-RAW-DOWNLOADER/tree/3b2c0eae6d0df83d08284bd25c2f068a6ca9bfb2/reports/raw-register/20261027_v1)

[盤點基準ChatGPT完整包](https://chatgpt.com/library?file_id=libfile_c96c12a2ed9081918c202d7195e1aa39&account_id=personal)

本規範以版本化表格、JSON、複核證據與來源程式雜湊索引保存。尚未新增排程、變更現有重試/權限，或執行市場補下載。下一階段是把37條契約逐條映射到現有檢查器與缺失任務，再驗證可上線的修補方案。
'''
(O/'JARVIS_七大來源錯誤處理與驗收規範_20261027.md').write_text(md)
# Reproducibility and provenance for the read-only review.
for src in [pathlib.Path('review_scan.py'),pathlib.Path('make_acceptance.py'),pathlib.Path('finish_acceptance.py')]:
 (O/src.name).write_bytes(src.read_bytes())
validation={'spec_version':'JARVIS_RAW_ACCEPTANCE_20261027_V1','rule_count':37,'sources':['TWSE','TPEx','MOPS','FinMind','TAIFEX','TDCC','NDC'],'register_units_scanned':337023,'rules_unique_and_required_columns_nonempty':True,'review_findings':len(findings),'probe_is_synthetic':True,'raw_values_revalidated':False,'scheduler_changes':0,'closed_tasks':0}
(O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
fs=[p for p in O.iterdir() if p.is_file() and p.suffix not in ['.zip','.ndjson'] and p.name!='manifest.json']
(O/'manifest.json').write_text(json.dumps({p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in fs},ensure_ascii=False,indent=2))
with zipfile.ZipFile(O/'JARVIS_七大來源驗收規範與複核證據_20261027.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in fs+[O/'manifest.json']:z.write(p,p.name)
print('packaged',len(fs),'files')
