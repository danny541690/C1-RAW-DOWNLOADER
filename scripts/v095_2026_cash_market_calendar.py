"""Verified 2026 Taiwan equity cash market holidays (TWSE published 115 calendar).
This is specifically for TSE/OTC daily cash OHLCV, not TDCC, TAIFEX or NDC.
The date iteration/cursor positions are intentionally never changed by this filter.
"""
import datetime as dt
CLOSED={
    "2026-01-01",
    "2026-02-12","2026-02-13","2026-02-16","2026-02-17",
    "2026-02-18","2026-02-19","2026-02-20","2026-02-27",
    "2026-04-03","2026-04-06","2026-05-01","2026-06-19",
    "2026-09-25","2026-09-28","2026-10-09","2026-10-26","2026-12-25"
}
SOURCE="https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html"
def is_verified_closed(day,source):
    return source in ("TWSE","TPEx") and day in CLOSED
