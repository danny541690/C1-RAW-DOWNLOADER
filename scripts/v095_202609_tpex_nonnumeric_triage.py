"""Actual September 2026 OTC raw OHLCV exception classification; read-only Drive.
Uses original signed archive validator and writes row-level evidence to Actions artifacts.
This classifies observed bytes; trading suspension/official status is NOT inferred.
"""
import json,os,collections,pathlib
from scripts.v095_202609_silver_ohlcv_candidate import svc,convert,num
OUT=pathlib.Path("v095_sep_tpex_triage");OUT.mkdir(exist_ok=True)
def classify(records,errors):
    index={(str(r["trade_date"]),r["stock_id"]):r for r in records}
    kinds=collections.Counter()
    perday=collections.Counter()
    samples=[]
    for err in errors:
        date,stock=err["date"],err["stock_id"]
        row=index[(date,stock)]
        volume=num(err["volume"])
        if volume is None:label="VOLUME_NOT_NUMERIC"
        elif volume>0:label="POSITIVE_VOLUME_OHLC_NOT_NUMERIC"
        elif volume==0:label="ZERO_VOLUME_OHLC_NOT_NUMERIC"
        else:label="NEGATIVE_VOLUME_FATAL"
        kinds[label]+=1;perday[date]+=1
        samples.append({"date":date,"stock_id":stock,"source_zip_id":row["source_zip_id"],
            "source_member":row["source_member"],"source_sha256":row["source_sha256"],
            "native_ohlc":err["native"],"volume":err["volume"],
            "status":label,"official_trading_status":"UNVERIFIED"})
    return {"total":len(errors),"by_kind":dict(kinds),"by_day":dict(sorted(perday.items())),
            "rows":samples,"all_rows_have_original_lineage":all(bool(x["source_member"] and x["source_sha256"]) for x in samples),
            "source_classification_not_pit":True,"classification_complete":len(samples)==len(errors)}
def main():
    s=svc()
    data,records,errors=convert(s,"TPEx")
    report=classify(records,errors)
    report["market"]="OTC";report["month"]="2026-09";report["rows_all"]=len(records)
    report["days"]=len({str(x["trade_date"]) for x in records})
    report["silver_candidate_sha256"]=__import__("hashlib").sha256(data).hexdigest()
    report["status"]="TRIAGED_NATIVE_EXCEPTIONS_NOT_OFFICIAL_STATUS_CERTIFIED"
    (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},ensure_ascii=False))
    assert report["classification_complete"] and report["all_rows_have_original_lineage"]
    assert report["total"]==sum(report["by_kind"].values())
if __name__=="__main__":main()
