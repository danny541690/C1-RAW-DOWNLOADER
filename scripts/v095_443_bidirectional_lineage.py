"""JARVIS v0.95: 443 indicator bidirectional candidate lineage and three-month PIT ledger.
443 rows are grounded in actual canonical catalog; source family hints are NOT
verified formula edges. No assumed first_published_at, warmup or QA PASS.
"""
import os,io,csv,json,re,hashlib,pathlib,datetime as dt,collections
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from v095_publication_gate import classify,TZ
CATALOG_ID="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
RULES=pathlib.Path("config/v095_data_validity_system_rules.json")
OUT=pathlib.Path("ultimate_r1_lineage");OUT.mkdir(exist_ok=True)
GOVERNANCE="1igeNb_PpOgiYV13_TB1rfEPNsAoisc_Z"
OPS="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
MONTHS=("2026-09","2026-10","2026-11")
# Map to domain *candidates*, never assert all fields or formulas are verified.
HINTS={
 "OHLCV/MASTER":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","MOPS_QUARTERLY_FINANCIALS"),
 "OHLC":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"),
 "OHLCV/SHARES":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","MOPS_QUARTERLY_FINANCIALS"),
 "OHLC/BENCHMARK":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"),
 "OHLC/UNIVERSE":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"),
 "MONTHLY_REVENUE":("MOPS_MONTHLY_REVENUE",),
 "QUARTERLY_FINANCIAL":("MOPS_QUARTERLY_FINANCIALS",),
 "PRICE/PIT_FINANCIAL":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","MOPS_QUARTERLY_FINANCIALS"),
 "TDCC/OWNERSHIP":("TDCC_WEEKLY_OWNERSHIP",),
 "INST_DAILY":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"), # institutional flows need separate dataset contracts
 "BROKER/MARGIN":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"), # not certified: detailed broker feeds absent
 "SECTOR/CONSTITUENTS":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET"), # needs PIT sector membership
 "MULTI_DOMAIN":("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","MOPS_MONTHLY_REVENUE","MOPS_QUARTERLY_FINANCIALS","TDCC_WEEKLY_OWNERSHIP")
}
EXTRA={
 "INST_DAILY":["INSTITUTIONAL_FLOW_EXACT_DATASET_UNREGISTERED"],
 "BROKER/MARGIN":["BROKER_BRANCH_AND_MARGIN_DATASET_CONTRACT_NOT_REGISTERED"],
 "SECTOR/CONSTITUENTS":["HISTORICAL_SECTOR_MEMBERSHIP_DATASET_REQUIRED"],
 "OHLCV/MASTER":["SHARES_OUT_FLOAT_HISTORY_MAY_REQUIRE_CORPORATE_ACTIONS"],
 "MULTI_DOMAIN":["FULL_FEATURE_DAG_AND_RISK_POLICY_REQUIRED"]
}
def sha(b):return hashlib.sha256(b).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],
 client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
 token_uri="https://oauth2.googleapis.com/token",
 scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def rows_csv(records,columns):
 buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=columns,extrasaction="ignore",lineterminator="\n");w.writeheader()
 for x in records:
  w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in x.items()})
 return ("\ufeff"+buf.getvalue()).encode()
def put(s,parent,name,blob,cache):
 matches=[x for x in cache if x["name"]==name]
 if len(matches)>1:raise ValueError("DUPLICATE_LINEAGE_NAME")
 if matches:
  fid=matches[0]["id"];action="REUSED"
 else:
  fid=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/octet-stream"),fields="id").execute()["id"];action="CREATED"
 if sha(s.files().get_media(fileId=fid).execute())!=sha(blob):raise ValueError("LINEAGE_DRIVE_SHA_READBACK_MISMATCH")
 return {"id":fid,"action":action,"sha256":sha(blob)}
def listing(s,parent):
 out=[];tok=None
 while True:
  z=s.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name)",pageSize=1000,pageToken=tok).execute()
  out+=z.get("files",[]);tok=z.get("nextPageToken")
  if not tok:return out
def window_hint(ind):
 # Suffixes are candidate minimum periods only: no formula certification.
 match=re.search(r"(?:_|^)(?:1|5|10|20|50|60|120|240)(?:D)?(?:_|$)",ind)
 if match:
  digit=re.search(r"\d+",match.group(0));return int(digit.group()) if digit else None
 m=re.match(r"MA(5|10|20|60|120|240)(?:_|$)",ind)
 if m:return int(m.group(1))
 if ind.startswith("REVENUE_24M"):return 24
 if ind.startswith("REVENUE_6M"):return 6
 if ind.startswith("REVENUE_3M"):return 3
 return None
def main():
 s=svc();b=s.files().get_media(fileId=CATALOG_ID).execute();cat=json.loads(b);inds=cat["indicators"]
 if len(inds)!=443 or len({x["id"] for x in inds})!=443:raise ValueError("CATALOG_443_INVALID")
 policy=json.loads(RULES.read_text());contracts={x["dataset_id"]:x for x in policy["sources"]}
 forward=[];reverse=collections.defaultdict(list);audit=[];unknown=collections.Counter()
 now=dt.datetime.now(TZ)
 for item in inds:
  key=item["id"];family=item.get("legacy_source","UNKNOWN");datasets=HINTS.get(family,())
  notes=EXTRA.get(family,[])
  if not datasets:unknown[family]+=1
  formula=item.get("formula") or "DEFINITION_PENDING"
  record={"indicator_id":key,"name":item.get("name"),"group":item.get("group"),"unit":item.get("unit"),
    "legacy_source":family,"candidate_dataset_ids":list(datasets),"unresolved_dependencies":notes,
    "formula_defined":formula!="DEFINITION_PENDING","formula_catalog":formula,
    "warmup_period_hint":window_hint(key),"warmup_hint_certified":False,
    "bronze_silver_mapping_status":"HINT_ONLY_UNTIL_EXACT_FIELD_AND_SOURCE_SHA_VALIDATED",
    "formula_PIT_verified":bool(item.get("pit_verified",False)),
    "catalog_queryable":bool(item.get("queryable",False)),
    "catalog_original_sha256":sha(b)}
  forward.append(record)
  for dataset in datasets:reverse[dataset].append(key)
  for month in MONTHS:
   states=[];release={}
   for dataset in datasets:
    if dataset in ("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","MOPS_MONTHLY_REVENUE","TDCC_WEEKLY_OWNERSHIP","TAIFEX_DAILY","NDC_BUSINESS_CYCLE","CUSTOMS_TRADE","MOEA_INDUSTRIAL_PRODUCTION"):
     states.append(classify(dataset,month,now)["status"])
    else:states.append("UNMAPPED_PRODUCT_CALENDAR")
   audit.append({"indicator_id":key,"month":month,"group":item.get("group"),
     "candidate_dataset_ids":list(datasets),"release_statuses":states,
     "value_status":"NOT_CERTIFIED_UNTIL_INPUT_DATASET_ROW_COVERAGE_CHECKED",
     "warmup_hint":record["warmup_period_hint"],"warmup_verified":False,
     "official_first_published_at":None,"release_version":None,
     "gold_to_silver_sha_match":None,"silver_to_bronze_sha_match":None,
     "dataset_complete":False,"formula_pass":False,"PIT_pass":False,"bidirectional_verified":False,
     "acceptance":"BLOCK","reason":"UNVERIFIED_FORMULA_OR_SOURCE_INPUT_OR_PIT",
     "source_family_hint_only":True})
 # Full reverse mapping preserves every candidate edge but not source-file identity.
 if len(audit)!=1329:raise ValueError("MONTH_AUDIT_NOT_1329")
 if any(set(reverse[k])!={q["indicator_id"] for q in forward if k in q["candidate_dataset_ids"]} for k in reverse):
  raise ValueError("FORWARD_REVERSE_INCONSISTENT")
 reverse_rows=[{"dataset_id":d,"source":contracts.get(d,{}).get("source","UNREGISTERED"),
    "dependent_indicator_count":len(ids),"indicator_ids":sorted(ids),
    "edge_status":"CANDIDATE_NOT_SHA_VERIFIED"} for d,ids in sorted(reverse.items())]
 report={"schema":"JARVIS_V095_443_BIDIRECTIONAL_LINEAGE_R1","run_context":"2026-09_to_2026-11_validity_audit",
  "catalog_id":CATALOG_ID,"catalog_sha256":sha(b),"catalog_count":443,
  "forward_rows":len(forward),"reverse_datasets":len(reverse_rows),"monthly_audit_rows":len(audit),
  "source_family_not_mapped":dict(unknown),"formula_catalog_pending":sum(x["formula"]=="DEFINITION_PENDING" for x in inds),
  "all_months_production_certified":False,"full_formula_DAG_certified":False,"PIT_certified":False,
  "interpretation":"Candidate source-family mapping, not evidence of complete 443 formula or SHA lineage. Each of 1329 month rows BLOCK until measured."}
 artifacts={
 "JARVIS_V095_443_GOLD_TO_SILVER_BRONZE_R1.csv":rows_csv(forward,list(forward[0])),
 "JARVIS_V095_443_BRONZE_SILVER_TO_GOLD_R1.csv":rows_csv(reverse_rows,list(reverse_rows[0])),
 "JARVIS_V095_443_202609_11_PIT_AUDIT_R1.csv":rows_csv(audit,list(audit[0])),
 "JARVIS_V095_443_BIDIRECTIONAL_LINEAGE_SUMMARY_R1.json":json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2).encode()}
 dest=listing(s,GOVERNANCE);locations={}
 for name,data in artifacts.items():
  stem,ext=name.rsplit(".",1)
  versioned=stem+"_"+sha(data)[:12]+"."+ext
  locations[versioned]=put(s,GOVERNANCE,versioned,data,dest)
 (OUT/"registry_receipt.json").write_text(json.dumps({"summary":report,"drive_files":locations},ensure_ascii=False,indent=2))
 print(json.dumps({"run_id":report["run_id"],"summary":report,"drive_files":locations},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
