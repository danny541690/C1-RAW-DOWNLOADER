# JARVIS C1 v0.95｜2026/09 R5 單月修補／對帳結果（2026-11-06）

## 真實執行證據
GitHub Actions Run 42153892333 SUCCESS，實際讀取 Google Drive 兩份 Silver Parquet、五份既有 Gold Parquet 與 v0.93 的 443 指標 ID 目錄。Google Drive QA 回讀 ID `1i6wcPhfkR_NjeaVFgPXQybtsVUbsNDb7`。成功表示本次稽核程式執行完成，不代表全面 Gold、公式或 PIT 生產核准。

### 一、價格來源修補清單
- TSE 21,860 列：21,803 有效價、41 有量無價、16 零量無價。
- OTC 17,762 列：17,350 有效價、255 有量無價、157 零量無價。
- 共 296 筆有量無價、173 筆零量無價，合計469。根據 R4，原始 OHLC 分別是 '--' / '---'，非擅自轉為缺值；有量亦不能直接推斷是一般交易 OHLC。逐筆清單包含股票日期、成交量、原行情及來源 SHA；保留於 GitHub Run 的 `price_queue.json` artifact。
- 待查：同日同證券一般交易／盤後零股／其他交易場別區分、停復牌及官方來源解釋。只允許「**同一交易場別、同一價量口徑、有官方正式數值**」替換，否則保持 NULL 並附原因。不得除成交額/股數還原 OHLC。**尚未取得296筆的有效替換價，不得視為296筆已修好**。
- 無價但零量 173 筆列候選合法無價，需檢查停復牌及市場身分，不視為469個下載失敗。已驗證官方原件不可再無條件重抓。

### 二、443 項對照與月度適用性
- 本輪 443 ID 已逐項寫出 `indicator_mapping.json`。
- 其中 **21** 項能對上現有五個 Gold Parquet 的實際欄位且觀測到值或欄位，狀態為 `FIELD_EXISTS_FORMULA_UNCERTIFIED`；**422** 項標為 `NOT_YET_MAPPED_NOT_PROVEN_MISSING`，不是422項確實缺值或不能計算，也不是21項公式已核准。這是**目前明確欄位別名對照進度**，非443項 Gold 完成率。
- 必須繼續建構全443項公式欄位 DAG、有效窗口、母體及映射；不適用的60/120/240日、24月、TTM不能列為單月失敗。57項主力／分點直接依賴XQ，來源未完整時保持停用。
- 九月現有短期SMA5/10/20、營收、當日價量等子集合已產生，但不能依21/443推估整體實算比例。

### 三、歷史 PIT 兩種驗收口徑
1. `MONTHLY_DESCRIPTIVE_ASOF_2026-11-06`：九月資料在十一月回顧可用，假設來源可追溯；不應要求所有長期暖機資料齊備。
2. `HISTORICAL_BACKTEST_ASOF_DATE`：必須取 `first_published_at`／`available_at`／`revision_at`／公司行動／當時成分與證券身分。例如2026年九月營收通常在2026年十月公布，不得在9月30日使用事後值；公開日期不能用下載日期冒充。
3. 上述第二類未提供完整公告時點，保持 `PIT_BLOCKED`，不影響第一類描述性的已核實部分。

### 四、排程經驗與修復
- 舊的再抓排程持續報 `PRODUCTION_RELEASE_BLOCKED_CODE_CHANGED`，實質是舊版 release code SHA 與現在程式不同；必須另行重簽／重新測試舊 release，不能把這個故障當成九月行情原始資料缺失，更不能跳過核准。
- TDCC 原始 10,949 檔與九月 Silver 276,097 列四週結構均已驗收，R3 controller 已修正，會看 Drive 實際 QA 而非舊 checkpoint `running`。
- 單日總控保持每日一次，R5 專項使用按需觸發及可追溯 artifact，避免每半小時重新讀取完整 Parquet。
- Bronze v0.93 只讀→官方定點查缺→FinMind Free 僅相容補缺；Silver 有效值與原缺值都保留；Gold 不推算事後數據也不填0。GitHub 執行成功與資料QA/PIT分開。

## 已執行／仍待辦
- DONE：469筆原因與原字串分類、443清冊逐項mapping檔、11/06描述性 vs 歷史PIT拆分、R5真實Drive輸入和QA輸出/保存。
- PENDING：296筆的相同口徑官方補值可行性逐筆判定、173筆無成交原因終驗、422個尚未建立明確欄位對照的 ID 機器級映射與公式核准、歷史PIT各來源公告證據索引、ChatGPT標準化Gold查詢執行器。
- 九月月度驗收狀態：`MONTH_SCOPE_PARTIAL`，不能標記 `FULL_443_LIVE`。
