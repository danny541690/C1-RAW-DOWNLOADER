#!/usr/bin/env python3
"""JARVIS 0.98 matched FinMind Free/Backer observational schema and history probes.
Identical params with independent repos, immutable reports. Source docs key
columns are descriptive, not a full required-field contract.
"""
import csv,datetime as dt,hashlib,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error
PLAN=os.environ["FINMIND_AUDIT_PLAN"].upper()
if PLAN not in ("FREE","BACKER"):raise SystemExit("INVALID_PLAN")
TOKEN=os.environ.get("FINMIND_BACKER_TOKEN","").strip() if PLAN=="BACKER" else ""
if PLAN=="BACKER" and not TOKEN:raise SystemExit("BACKER_TOKEN_MISSING")
OUT=pathlib.Path("v098_finmind_matched_audit");OUT.mkdir(exist_ok=True)
DATASETS=[
 ("TaiwanStockPrice","stock","day"),("TaiwanStockPriceAdj","stock","day"),
 ("TaiwanStockPER","stock","day"),("TaiwanStockInstitutionalInvestorsBuySell","stock","day"),
 ("TaiwanStockMarginPurchaseShortSale","stock","day"),
 ("TaiwanStockShareholding","stock","day"),("TaiwanStockHoldingSharesPer","stock","week"),
 ("TaiwanStockMonthRevenue","stock","year"),("TaiwanStockFinancialStatements","stock","year"),
 ("TaiwanStockBalanceSheet","stock","year"),("TaiwanStockCashFlowsStatement","stock","year"),
 ("TaiwanStockMarketValue","stock","day"),("TaiwanBusinessIndicator","macro","year"),
]
YEARS=[2000,2008,2013,2018,2024,2026]
URL="https://api.finmindtrade.com/api/v4/data"
DOC="https://raw.githubusercontent.com/FinMind/FinMind-MCP/master/knowledge/datasets.md"
def registry():
 with urllib.request.urlopen(urllib.request.Request(DOC,headers={"User-Agent":"JARVIS-C1-AUDIT-v098"}),timeout=30) as f:content=f.read()
 out={}
 for block in re.split(r"(?m)^### ",content.decode("utf-8-sig"))[1:]:
  name=block.splitlines()[0].strip()
  tier=re.search(r"(?m)^-\s*\*\*Tier:\*\*\s*(.+)$",block)
  keys=re.search(r"(?m)^-\s*\*\*Key columns:\*\*\s*(.+)$",block)
  out[name]={"tier":tier.group(1).strip() if tier else "UNKNOWN",
             "key_column_documentation":keys.group(1).strip() if keys else ""}
 return out,hashlib.sha256(content).hexdigest()
def req_one(ds,source_type,mode,year):
 if mode=="day":start=f"{year}-01-02";end=f"{year}-01-12"
 elif mode=="week":start=f"{year}-01-01";end=f"{year}-02-15"
 else:start=f"{year}-01-01";end=f"{year}-12-31" if year!=2026 else "2026-11-20"
 q={"dataset":ds,"start_date":start,"end_date":end}
 if source_type=="stock":q["data_id"]="2330"
 req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(q),
  headers={"Accept":"application/json","User-Agent":"JARVIS-v0.98-Matched-FinMind-Audit",
    **({"Authorization":"Bearer "+TOKEN} if TOKEN else {})})
 try:
  with urllib.request.urlopen(req,timeout=45) as r:
   status=r.status;raw=r.read(6000001)
  if len(raw)>6000000:return q,{"state":"SIZE_LIMIT","http_status":status}
  obj=json.loads(raw.decode("utf-8-sig"))
  if obj.get("status")!=200:return q,{"state":"API_REJECTED","api_status":obj.get("status"),"http_status":status}
  data=obj.get("data")
  if not isinstance(data,list):return q,{"state":"INVALID_ARRAY","http_status":status}
  if not data:return q,{"state":"EMPTY","http_status":status,"rows":0}
  if not all(isinstance(x,dict) for x in data):return q,{"state":"BAD_ROW"}
  cols=sorted(set().union(*(set(row) for row in data)))
  types={k:sorted({type(row[k]).__name__ for row in data if k in row}) for k in cols}
  dates=sorted({str(x.get("date"))[:10] for x in data if x.get("date")})
  norm=sorted(data,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
  sha=hashlib.sha256(json.dumps(norm,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
  return q,{"state":"PASS","http_status":status,"rows":len(data),"columns":cols,"field_types":types,
    "first_date":dates[0] if dates else None,"last_date":dates[-1] if dates else None,
    "canonical_sha256":sha,"values_in_period_only":True}
 except urllib.error.HTTPError as e:return q,{"state":"HTTP_ERROR","http_status":e.code}
 except Exception as e:return q,{"state":"ERROR","error_type":type(e).__name__}
def main():
 docs,doc_sha=registry();rows=[]
 for ds,kind,mode in DATASETS:
  for year in YEARS:
   params,res=req_one(ds,kind,mode,year)
   doc=docs.get(ds,{})
   rows.append({"dataset":ds,"plan":PLAN,"year":year,"params":params,
     "official_registry_tier":doc.get("tier","NOT_IN_DOCUMENT"),
     "documented_key_columns":doc.get("key_column_documentation",""),
     **res})
   print(json.dumps({"dataset":ds,"year":year,"state":res["state"],"rows":res.get("rows",0),
    "fields":len(res.get("columns",[]))},ensure_ascii=False),flush=True)
   if res.get("http_status")==429:break
   time.sleep(.23)
 summary={"plan":PLAN,"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"dataset_count":len(DATASETS),
 "matched_query_count":len(rows),"success":sum(r["state"]=="PASS" for r in rows),
 "empty":sum(r["state"]=="EMPTY" for r in rows),
 "fail":sum(r["state"] not in ("PASS","EMPTY") for r in rows),
 "registry_sha256":doc_sha,"official_registry_url":DOC,
 "all_history_coverage_certified":False,"date_window":"Six bounded year-vintage samples 2000,2008,2013,2018,2024,2026",
 "sources_included":["FinMind_"+PLAN],"queries":rows}
 (OUT/"report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"observed_schemas.csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.writer(f);w.writerow(["plan","dataset","year","official_registry_tier","status","rows","first_date","last_date","column_names","field_types","canonical_sha256"])
  for r in rows:w.writerow([PLAN,r["dataset"],r["year"],r["official_registry_tier"],r["state"],
    r.get("rows",""),r.get("first_date",""),r.get("last_date",""),"|".join(r.get("columns",[])),
    json.dumps(r.get("field_types",{}),ensure_ascii=False),r.get("canonical_sha256","")])
 print("FINMIND_MATCHED_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="queries"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
