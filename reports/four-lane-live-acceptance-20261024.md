# 四路檢查：實際隔離 Drive 與跨工作續跑驗收

2026-10-24 台灣時間14:41完成。Run [40071042568](https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40071042568) 全部四個工作成功；測試前130項相關回歸通過。

- 實際Drive寫入後，在GitHub進度提交前中斷子程序；下一工作使用真實租約到期時間接管，fence由2至3，過期寫入者遭拒。
- 兩個實際GitHub CAS競爭者僅一個取得鎖。
- 讀取既有六月財報原始ZIP，5份、4975個數值儲存格完成嚴格轉換、隔離Drive寫入、SHA回讀及原生儲存格對照。
- 另一個GitHub工作重新執行後，5份輸出的Drive file ID與SHA全部相同，未產生重複檔案。
- 20家公司回應僅16家公司的一份維持來源內容不完整（缺9103、9105、9110、9136），不補造或計入成功。
- 原始來源網站下載請求0、正式RAW寫入0。舊一至四維持暫停；新四路正式排程未啟用。

[隔離測試輸出](https://drive.google.com/drive/folders/1r5tQaEnjby_UNV1tsCuRftH6GKa2PMS2)。詳細機器證據見 four-lane-live-acceptance-proof-20261024.json 及run artifacts。

這次驗證sandbox adapter及財報重解析的真實跨服務行為，不等於四路正式月份工作流程全量驗收；整月隊列公平性／多路相遇、失效路由及缺公司來源補抓仍待驗證。數值往返相符不代表會計語意與PIT已通過，production gate保持BLOCKED。
