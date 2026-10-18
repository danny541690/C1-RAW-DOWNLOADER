"""Deterministic production manifest/report builder. Does not certify market coverage."""
import csv,io,json,hashlib
from scripts.production_gates import SOURCES,raw_segments,coverage_status

def build_month(year,month,units,expected_by_source=None):
    expected_by_source=expected_by_source or {}
    grouped={}
    for source in SOURCES:
        group=[u for u in units if u["source"]==source]
        saved=[u for u in group if u.get("status")=="SAVED_BASIC_VALID"]
        pending=[u for u in group if u.get("status")!="SAVED_BASIC_VALID"]
        grouped[source]={"raw_path":"/".join(raw_segments(year,source,month)),
            "scheduled":len(group),"saved_basic_valid":len(saved),
            "missing":len(pending),"coverage":coverage_status(expected_by_source.get(source),len(saved)),
            "requests":sum(int(u.get("attempts",0)) for u in group),
            "bytes":sum(int(u.get("bytes",0)) for u in saved)}
    missing=[u for u in units if u.get("status")!="SAVED_BASIC_VALID"]
    report={"year":year,"month":month,"sources":grouped,"scheduled":len(units),
        "saved_basic_valid":sum(v["saved_basic_valid"] for v in grouped.values()),
        "missing":len(missing),"qa_verified":False,
        "market_coverage_complete":False,"status":"FINISHED_WITH_GAPS" if missing else "BASIC_COMPLETE_COVERAGE_UNKNOWN"}
    f=io.StringIO()
    cols=["key","source","status","attempts","last_error"]
    w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
    w.writeheader();w.writerows(missing)
    md=f"# {year}-{month:02d} 月度下載報告\n\n基本保存：{report['saved_basic_valid']}/{report['scheduled']}；缺漏：{len(missing)}；全市場涵蓋率：未驗證。\n"
    return {"MONTHLY_PROGRESS.json":json.dumps(report,ensure_ascii=False,indent=2)+"\n",
            "MISSING_UNITS.csv":f.getvalue(),"MONTHLY_PROGRESS.md":md}
