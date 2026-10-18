"""Safe annual month scheduler acceptance test: simulated sources only.

Exercises 12-month forward progress, deferred repairs, bounded retries and
checkpoint-based reruns. No market HTTP requests, no Drive writes.
"""
import argparse
import json
from pathlib import Path
from scripts.batch_engine import execute_month

SOURCES=("TWSE","TPEx","MOPS","FinMind")

def simulate(year,root):
    counts={}
    monthly=[]
    for month in range(1,13):
        units=[{"key":f"{source}-{year}-{month:02d}","source":source}
               for source in SOURCES]
        def fetch(unit):
            key=unit["key"]
            counts[key]=counts.get(key,0)+1
            if key==f"TPEx-{year}-03": return {"ok":False,"error":"HTTP_503"}
            if key==f"MOPS-{year}-07": return {"ok":False,"error":"HTTP_403"}
            return {"ok":True,"data":b"SIMULATION_NOT_REAL_MARKET_DATA"}
        monthly.append(execute_month(year,month,units,fetch,lambda u,d:True,root))
    missing=[]
    for month in range(1,13):
        path=Path(root)/str(year)/f"{month:02d}"/"checkpoint.json"
        ledger=json.loads(path.read_text())
        for source in SOURCES:
            key=f"{source}-{year}-{month:02d}"
            unit=ledger[key]
            if unit["status"]!="SAVED_BASIC_VALID":
                missing.append({"year":year,"month":month,"source":source,
                                "unit":key,"status":unit["status"],
                                "attempts":unit["attempts"],
                                "last_error":unit.get("last_error")})
    summary={"year":year,"simulated":True,"actual_market_requests":0,
             "google_drive_uploaded":False,"scheduled_units":48,
             "saved_units":sum(x["saved_basic_valid"] for x in monthly),
             "missing_units":len(missing),"months_processed":12,
             "deferred_repair_queue":missing,"source_requests":sum(counts.values())}
    out=Path(root)/str(year)
    (out/"ANNUAL_SIMULATION_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
    (out/"REPAIR_QUEUE.json").write_text(json.dumps(missing,indent=2)+"\n")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--year",type=int,default=2024)
    p.add_argument("--root",default="output/annual-simulation")
    args=p.parse_args()
    result=simulate(args.year,args.root)
    print(json.dumps({k:v for k,v in result.items() if k!="deferred_repair_queue"}))
    assert result["saved_units"]==46 and result["missing_units"]==2
if __name__=="__main__":main()
