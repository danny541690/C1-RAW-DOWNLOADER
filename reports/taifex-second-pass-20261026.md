# 期交所第二輪檢查與缺失補正（2026-10-26）

使用者指定分工：排程6=DESC，最新官方可取得日期往2013-01-01；排程6-1=ASC，2000-01-01往2012-12-31。兩者分區不重疊。這次交換工作流程方向，但狀態目錄仍按方向沿用：DESC=TAIFEX_INDEPENDENT_STAGE06，ASC=TAIFEX_INDEPENDENT_STAGE06_ASC；不移動RAW、不清空收據或來源重試歷程。

兩條均使用 --audit-round 2。新審核標記 REMOTE_RAW_SECOND_PASS_20261026 使上一輪PASS的原檔重新回讀SHA與原生格式；每批最多24筆，後續喚醒沿收據繼續。第一輪raw_audit另存raw_audit_history。已完成第二輪且SHA未變者跳過；通過原檔不向官方重抓。遺失的遠端RAW由原始請求補抓；SHA/內容不符保留原檔與integrity_hold，不能盲目覆寫。來源空回應、未提供歷史、無法重建舊快照、重試耗盡均保持可追溯缺口，不以假檔或後日快照冒充。

既有V8.2官方路由鏡像、已驗證別名去重、短冷卻恢復及有限傳輸重試保留。沒有重設REPAIR_REVISION，故不因第二輪取消原本重試上限。每次STATUS保存輸出TAIFEX_LIVE_STATUS，包含方向、排程號、第二輪、本批檢查/來源請求/保存數、計畫未嘗試及未解決數；這些不是全市場完整驗收。

本地734項測試通過，新增驗證第二輪重新回讀一次、原file_id/來源attempts不變、第一輪紀錄保留、2012/2013分區及兩工作流方向。部署commit ecbd2130819fcc0a31abc1c1690c3c832040f6e6。

上線批次：6=https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40349222152 ；6-1=https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40349222143 。仍須查核雲端測試及正式下載步驟結果，不把排隊或綠燈當資料補齊。
