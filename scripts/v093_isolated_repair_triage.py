"""Classify all 322-month metadata into actionable non-certifying queues.

Consumes GitHub Actions artifact from a successful read-only Drive inventory.
Never assumes an empty month means a downloadable source dataset exists.
"""
import collections
import json

SOURCES=("TWSE","TPEx","MOPS","FinMind")

def classify(shards):
    months={}
    for shard in shards:
        if shard.get("read_only") is not True or shard.get("certified")!=0:
            raise ValueError("UNTRUSTED_OR_CERTIFIED_SHARD")
        for month,source_rows in shard["months"].items():
            if month in months:raise ValueError("DUPLICATE_MONTH")
            months[month]=source_rows
    expected={f"{year}-{m:02d}" for year in range(2000,2027) for m in range(1,13) if f"{year}-{m:02d}"<="2026-10"}
    if set(months)!=expected:raise ValueError("INCOMPLETE_SCOPE")
    status=collections.Counter()
    by_source={s:collections.Counter() for s in SOURCES}
    by_year={}
    queues={"EMPTY_REVIEW":[],"DUPLICATE_NAME_QUARANTINE":[],"ZERO_BYTE_QUARANTINE":[],"PRESENT_PENDING_QA":[],"STRUCTURAL_ERROR":[]}
    files=0
    for month in sorted(months,reverse=True):
        row=months[month]
        if set(row)!=set(SOURCES):raise ValueError("INVALID_SOURCES_"+month)
        yr=month[:4]
        by_year.setdefault(yr,{"empty":0,"present":0,"duplicate":0,"zero_byte":0})
        for source in SOURCES:
            v=row[source]
            st=v["status"]
            status[st]+=1
            by_source[source][st]+=1
            files+=v["file_count"]
            item={"month":month,"source":source,"status":st,"file_count":v["file_count"],"zip_count":v["zip_count"],"other_count":v["other_count"]}
            if st=="EMPTY_MONTH_FOLDER":
                if v["file_count"]!=0:raise ValueError("NONEMPTY_MARKED_EMPTY")
                by_year[yr]["empty"]+=1
                item["action"]="VERIFY_EXPECTED_DATA_AND_ALTERNATE_FORMATS_BEFORE_BACKFILL"
                queues["EMPTY_REVIEW"].append(item)
            elif st=="FILES_PRESENT_PENDING_QA":
                by_year[yr]["present"]+=1
                item["action"]="HASH_CRC_SCHEMA_NUMERIC_PIT_VALIDATION"
                queues["PRESENT_PENDING_QA"].append(item)
            else:
                item["action"]="INVESTIGATE_STRUCTURE"
                queues["STRUCTURAL_ERROR"].append(item)
            if v.get("duplicate_names"):
                by_year[yr]["duplicate"]+=len(v["duplicate_names"])
                for name in v["duplicate_names"]:
                    queues["DUPLICATE_NAME_QUARANTINE"].append({"month":month,"source":source,"filename":name,"action":"COMPARE_FILE_IDS_AND_HASHES_NO_AUTO_DELETE"})
            if v.get("zero_size",0):
                by_year[yr]["zero_byte"]+=v["zero_size"]
                queues["ZERO_BYTE_QUARANTINE"].append({"month":month,"source":source,"count":v["zero_size"],"action":"RETRY_AND_QUARANTINE"})
    if len(months)!=322 or sum(status.values())!=1288:raise ValueError("BAD_COUNTS")
    return {"months":322,"source_month_pairs":1288,"files":files,"status_counts":dict(status),"by_source":{k:dict(v) for k,v in by_source.items()},"by_year":by_year,"queue_sizes":{k:len(v) for k,v in queues.items()},"queues":queues,"certified_months":0,"production_writes":0,"review_only":True}
