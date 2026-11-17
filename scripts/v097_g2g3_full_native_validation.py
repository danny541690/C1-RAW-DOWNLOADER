#!/usr/bin/env python3
"""Strict bounded full-file *structural* validation for G2/G3, native bytes only.

This is NEVER an official schema certification: source-specific key/units,
PIT revision, security identity and authoritative version are external gates.
JSONL and CSV may contain many rows, so cap per-member bytes and remain HOLD
rather than silently sample and label a full-file PASS.
"""
import csv, datetime, io, json, math, re
from collections import Counter
from scripts.v097_v3_contract_registry import infer,normalize
MAX_BYTES=8*1024*1024
MAX_ROWS=300000
DATE_FIELDS={"date"}
MONTH_FIELDS={"period"}
CODE_FIELDS={"code","contract","expiration"}
NUMBER_FIELDS={"open","high","low","close","volume","amount","revenue","holders","shares","percent","value","tier"}
def typed(field,value):
    if value is None or str(value).strip() in ("","--","-","NA","N/A","null","None"):
        return "NULL_POLICY_PENDING"
    s=str(value).strip().replace(",","")
    if field in DATE_FIELDS:
        try:
            if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",s):
                y,m,d=map(int,re.split(r"[-/]",s))
            elif re.fullmatch(r"\d{7}",s):
                y,m,d=int(s[:3])+1911,int(s[3:5]),int(s[5:])
            elif re.fullmatch(r"\d{8}",s):
                y,m,d=int(s[:4]),int(s[4:6]),int(s[6:])
            else:return "DATE_FORMAT_PENDING"
            datetime.date(y,m,d)
            return "DATE_VALID"
        except ValueError:return "DATE_INVALID"
    if field in MONTH_FIELDS:
        if re.fullmatch(r"\d{4}[-/]\d{1,2}",s):
            y,m=map(int,re.split(r"[-/]",s))
            return "MONTH_VALID" if 1900<=y<=2200 and 1<=m<=12 else "MONTH_INVALID"
        return "MONTH_FORMAT_PENDING"
    if field in CODE_FIELDS:return "CODE_VALID" if 0<len(s)<=32 else "CODE_INVALID"
    if field in NUMBER_FIELDS:
        try:return "NUMBER_VALID" if math.isfinite(float(s)) else "NUMBER_INVALID"
        except ValueError:return "NUMBER_INVALID"
    return "TYPE_RULE_MISSING"
def decode_csv(blob):
    for enc in ("utf-8-sig","cp950","big5"):
        try:return list(csv.reader(io.StringIO(blob.decode(enc)))),enc
        except (UnicodeDecodeError,csv.Error):continue
    return None,None
def decode_json(blob,filename):
    if filename.lower().endswith(".jsonl"):
        try:
            rows=[json.loads(line) for line in blob.decode("utf-8-sig").splitlines() if line.strip()]
            return rows,"JSONL"
        except (ValueError,UnicodeDecodeError):return None,"JSONL_PARSE_FAILED"
    try:data=json.loads(blob.decode("utf-8-sig"))
    except (ValueError,UnicodeDecodeError):return None,"JSON_PARSE_FAILED"
    if isinstance(data,list):return data,"JSON"
    if isinstance(data,dict):
        for k in ("data","records","result"):
            if isinstance(data.get(k),list):return data[k],"JSON_ARRAY_WRAPPED"
    return None,"JSON_DATASET_PAYLOAD_UNSUPPORTED"
def full_scan(blob,path,src,era,original_header):
    res={"status":"NO_FULL_NATIVE_VALIDATION","source":src,"dataset_candidate":None,
         "era":era,"row_count":0,"field_errors":{},"key_duplicate_count":0,
         "full_file_scanned":False,"g2_verified":False,"g3_verified":False,
         "official_contract_attested":False,"release":False}
    if len(blob)>MAX_BYTES:return {**res,"status":"RESOURCE_LIMIT_FULL_SCAN"}
    contract=infer(src,original_header,era)
    res["dataset_candidate"]=contract.get("dataset_candidate")
    if contract.get("status")!="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED":
        return {**res,"status":"HEADER_OR_ERA_NOT_CERTIFIABLE"}
    mapping=contract["observed_fields"]
    if not mapping:return {**res,"status":"NO_FIELD_MAPPING"}
    low=path.lower()
    if low.endswith((".csv",".txt")):
        raw_rows,encoding=decode_csv(blob)
        if raw_rows is None:return {**res,"status":"CSV_PARSE_ERROR"}
        header_index=next((i for i,r in enumerate(raw_rows[:20]) if
            all(normalize(v) in {normalize(col) for col in r} for v in mapping.values())),None)
        if header_index is None:return {**res,"status":"HEADER_MISMATCH"}
        cols=raw_rows[header_index]
        indices={k:next((i for i,v in enumerate(cols) if normalize(v)==normalize(alias)),None)
                 for k,alias in mapping.items()}
        records=[{k:(r[pos] if pos is not None and pos<len(r) else None) for k,pos in indices.items()}
                 for r in raw_rows[header_index+1:] if r and any(str(v).strip() for v in r)]
        res["encoding"]=encoding
    elif low.endswith((".json",".jsonl")):
        data,encoding=decode_json(blob,path)
        if data is None or not isinstance(data,list) or not all(isinstance(r,dict) for r in data):
            return {**res,"status":"JSON_RECORDS_UNSUPPORTED","json_kind":encoding}
        records=[{k:next((val for key,val in r.items() if normalize(key)==normalize(alias)),None)
                  for k,alias in mapping.items()} for r in data]
        res["encoding"]=encoding
    else:return {**res,"status":"NATIVE_PARSER_NOT_IMPLEMENTED"}
    if len(records)>MAX_ROWS:return {**res,"status":"ROW_RESOURCE_LIMIT","row_count":len(records)}
    if not records:return {**res,"status":"EMPTY_DATA"}
    failures=Counter()
    keys=tuple(k for k in ("date","period","code","contract","expiration","tier") if k in mapping)
    seen=set();duplicates=0
    for record in records:
        for field,val in record.items():
            verdict=typed(field,val)
            if verdict not in ("DATE_VALID","MONTH_VALID","CODE_VALID","NUMBER_VALID"):
                failures[field+":"+verdict]+=1
        if keys:
            key=tuple(str(record.get(k,"")) for k in keys)
            if key in seen:duplicates+=1
            else:seen.add(key)
    res.update({"row_count":len(records),"full_file_scanned":True,
        "field_errors":dict(failures),"key_fields_candidate":list(keys),
        "key_duplicate_count":duplicates,"source_native_full_sha_checked":False})
    # Even a pass here is only provisional: official full contract key semantics,
    # published timestamps and unit semantics are still independently required.
    res["status"]="FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED" if not failures and not duplicates else "FULL_NATIVE_SHAPE_EXCEPTIONS"
    return res
def selftest():
    from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
    era=OFFICIAL_VERSIONS["FinMind"]["periods"][0]["id"]
    h=["date","stock_id","open","max","min","close","Trading_Volume","Trading_money"]
    a={"date":"2026-11-16","stock_id":"2330","open":1,"max":2,"min":1,"close":2,"Trading_Volume":3,"Trading_money":4}
    v=full_scan((json.dumps([a],ensure_ascii=False)).encode(),"f.json","FinMind",era,h)
    assert v["full_file_scanned"] and v["row_count"]==1 and v["status"]=="FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED"
    assert not v["g3_verified"] and not v["release"]
    assert full_scan((json.dumps([a,a])).encode(),"f.json","FinMind",era,h)["key_duplicate_count"]==1
    wrong={**a,"date":"2026-02-30"}
    assert full_scan(json.dumps([wrong]).encode(),"f.json","FinMind",era,h)["status"]=="FULL_NATIVE_SHAPE_EXCEPTIONS"
    assert full_scan((json.dumps(a)+"\n").encode(),"f.jsonl","FinMind",era,h)["row_count"]==1
    csvdata=(",".join(h)+"\n2026-11-16,2330,1,2,1,2,3,4\n").encode()
    assert full_scan(csvdata,"a.csv","FinMind",era,h)["full_file_scanned"]
    assert full_scan(b"x"*(MAX_BYTES+1),"a.csv","FinMind",era,h)["status"]=="RESOURCE_LIMIT_FULL_SCAN"
    print("G2G3_FULL_NATIVE_VALIDATION_NEGATIVE_TESTS_PASS")
if __name__=="__main__":
    if __import__("sys").argv[1:]==["selftest"]:selftest()
    else:raise SystemExit("selftest")
