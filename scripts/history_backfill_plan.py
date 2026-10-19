"""Generate historical backfill work inventory; no network or download side effects."""
import argparse,calendar,datetime,json,pathlib
REGISTRY=pathlib.Path(__file__).resolve().parents[1]/"config/history_source_registry.json"
def make_plan(end_date=None):
    policy=json.loads(REGISTRY.read_text(encoding="utf-8"))
    end=datetime.date.fromisoformat(end_date) if end_date else datetime.date.today()
    if end<datetime.date(1990,1,1):raise ValueError("end before historical range")
    jobs=[]
    for item in policy["sources"]:
        if item["documented_start"] is None:
            jobs.append({"source":item["source"],"dataset":item["dataset"],"state":"DISCOVER_EARLIEST_DATE","start":None,"access":item["access"],"priority":item["priority"]})
            continue
        start=datetime.date.fromisoformat(item["documented_start"])
        year,month=start.year,start.month
        while (year,month)<=(end.year,end.month):
            jobs.append({"source":item["source"],"dataset":item["dataset"],"year":year,"month":month,"state":"PLANNED_NOT_FETCHED","start":max(start,datetime.date(year,month,1)).isoformat(),"end":min(end,datetime.date(year,month,calendar.monthrange(year,month)[1])).isoformat(),"priority":item["priority"],"access":item["access"]})
            month+=1
            if month==13:year,month=year+1,1
    return {"policy":policy["schema_version"],"end_date":end.isoformat(),"planned_monthly_dataset_units":sum(x["state"]=="PLANNED_NOT_FETCHED" for x in jobs),"unknown_start_datasets":sum(x["state"]=="DISCOVER_EARLIEST_DATE" for x in jobs),"history_download_started":False,"jobs":jobs}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--end-date")
    p.add_argument("--summary-only",action="store_true")
    a=p.parse_args()
    out=make_plan(a.end_date)
    if a.summary_only:out={k:v for k,v in out.items() if k!="jobs"}
    print(json.dumps(out,ensure_ascii=False,indent=2))
