# 十一工作槽合併測試

已實作測試 PASS：{'run': 87, 'failures': 0, 'errors': 0, 'skipped': 0}。十一份預覽YAML驗證錯誤 0。

來源回應為fixture，檔案與Git為本機實際操作；不是新十一條的真實Drive閉環。

| 上線門檻 | 狀態 |
|---|---|
| source_executors | BLOCKED_NOT_INTEGRATED |
| distributed_fencing_and_immediate_continuation | BLOCKED_NOT_INTEGRATED |
| live_eleven_slot_fetch_save_reverify | NOT_RUN |
| one_time_legacy_shutdown_and_state_migration | NOT_RUN |
| real_rate_limits_and_three_day_throughput | NOT_RUN |

正式上線仍阻擋。保存舊狀態後一次停用舊觸發，再啟動新十一條；本次測試沒有停用任何線上排程。

## 真實GitHub跨runner狀態驗證結果

實際run40796907530成功：seed、11個獨立worker及全新verify runner全部成功。七個來源測試分支已保存並逐一讀回，11槽各attempts=1、RAW_BASIC_VERIFIED、full_acceptance=false。各commit與來源槽數見remote_control.json。這是遠端Git CAS控制層證據，不是市場來源資料驗收。

完整程式回歸run40796915722成功。本輪新實作的遠端CAS後端已有本機與真實GitHub證據；仍須串入正式來源executor與續派送服務。狀態分頁、真實市場HTTP、Google Drive回讀、一次停舊切新及三天吞吐驗收尚未完成，不可上線新十一條完整下載服務。
