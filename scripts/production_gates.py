"""Production-safe static contracts for yearly folders and coverage."""
from datetime import date
SOURCES=("TWSE","TPEx","MOPS","FinMind")
def month_days(year,month):
    if type(year)!=int or type(month)!=int or not 1990<=year<=2100 or not 1<=month<=12:raise ValueError("invalid period")
    nxt=date(year+1,1,1) if month==12 else date(year,month+1,1)
    return (nxt-date.resolution).day
def raw_segments(year,source,month):
    month_days(year,month)
    if source not in SOURCES:raise ValueError("unknown source")
    return (str(year),source,f"{year}-{month:02d}")
def coverage_status(expected,stored,numeric=False,pit=False):
    if expected is None:return "COVERAGE_UNKNOWN"
    if type(expected)!=int or type(stored)!=int or expected<=0 or not 0<=stored<=expected:raise ValueError("bad coverage")
    if stored<expected:return "PARTIAL"
    if not(numeric and pit):return "BASIC_ONLY"
    return "QA_VERIFIED"
