"""Aggregate 14 independent September-November lane receipts without merging data.

A successfully executed worker only confirms a diagnostic was run, not complete
market-data coverage. All formal release gates fail closed.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib
from v095_release_maturity import source_period_maturity,combined_state
from v095_publication_gate import classify as official_release_classify, TZ
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
DIR=pathlib.Path("ultimate_r1_3month")
OUT=pathlib.Path("ultimate_r1_aggregate");OUT.mkdir(exist_ok=True)
PARENT="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
MONTHS=("2026-09","2026-10","2026-11")
BRONZE=("BRONZE_TWSE","BRONZE_TPEX","BRONZE_MOPS","BRONZE_TDCC","BRONZE_TAIFEX","BRONZE_NDC")
SILVER=("SILVER_PRICE","SILVER_FUNDAMENTAL","SILVER_TDCC","SILVER_MACRO")
GOLD=("GOLD_TECHNICAL","GOLD_CHIP","GOLD_FINANCIAL","GOLD_CROSS_ASSET")
LANES=BRONZE+SILVER+GOLD
def sha(x):return hashlib.sha256(x).hexdigest()
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def main():
 run=os.environ.get("GITHUB_RUN_ID","local")
 entries={};bad=[];bronze={m:{} for m in MONTHS};silver={m:{} for m in MONTHS};gold={m:{} for m in MONTHS}
 for name in LANES:
  p=DIR/(name+".json")
  if not p.exists():
   bad.append({"lane":name,"reason":"MISSING_JOB_RECEIPT"});continue
  try:
   j=json.loads(p.read_text())
   if j.get("run_id")!=run or j.get("lane")!=name or j.get("inspection")!="COMPLETE_WITH_GAPS_TO_CLASSIFY":raise ValueError("RECEIPT_RUN_OR_INSPECTION_MISMATCH")
   entries[name]={"stage":j["stage"],"inspection":j["inspection"]}
   for m in MONTHS:
    row=j.get("months",{}).get(m)
    if not isinstance(row,dict):bad.append({"lane":name,"month":m,"reason":"NO_MONTH_EVIDENCE"});continue
    if name in BRONZE:
     bronze[m][name]={"observed_files":row.get("observed_files",0),
      "original_manifest_ids_present":row.get("legacy_09_present_ids"),
      "original_manifest_expected":row.get("legacy_09_expected_ids"),
      "source_complete_contract_certified":False}
    else:
     target=silver if name in SILVER else gold
     target[m][name]={"observed_objects_at_month_depth":row.get("observed_objects_at_month_depth",0),
      "matching_candidate_names":row.get("matching_name_candidates",0),
      "known_parquet_pass":row.get("bytes_and_parquet_pass_count",0),
      "sample_parquet_checked":row.get("parquet_byte_read_count",0),
      "formula_pit_certified":False}
  except Exception as e:bad.append({"lane":name,"reason":type(e).__name__+":"+str(e)[:160]})
 observed={m:sum(v.get("observed_files",0)>0 for v in bronze[m].values()) for m in MONTHS}
 source_cells=sum(observed.values())
 # Release maturity is separate from job success: never count folder existence
 # as an official dataset receipt. Each source-month gets a four-state verdict.
 maturity_by_month={}
 for month in MONTHS:
  maturity_by_month[month]={}
  for name,row in bronze[month].items():
   source=name.replace("BRONZE_","")
   source="TPEx" if source=="TPEX" else source
   try:
    maturity_by_month[month][source]=source_period_maturity(
      source,month,row.get("observed_files",0),
      has_error=any(z.get("lane")==name and z.get("month")==month for z in bad))
   except Exception as exc:
    bad.append({"lane":name,"month":month,"reason":"MATURITY_ERROR:"+str(exc)[:140]})
    maturity_by_month[month][source]={"acceptance":{"status":"ERROR","reason":"MATURITY_CALCULATION_ERROR","rmi":None}}
 # Canonical source-by-dataset release registry must be consulted, not merely
 # the month-folder-level source map. Publication expectations are distinct
 # from proof that individual stock rows existed at a historical as-of date.
 canonical_rules=json.loads(pathlib.Path("config/v095_data_validity_system_rules.json").read_text(encoding="utf-8"))
 if canonical_rules.get("schema") not in ("JARVIS_V095_DATA_VALIDITY_SYSTEM_RULES_V2","JARVIS_V095_DATA_VALIDITY_SYSTEM_RULES_V3"):
  raise ValueError("UNEXPECTED_CANONICAL_RULES_VERSION")
 dataset_release_matrix={}
 now=dt.datetime.now(TZ)
 source_to_gate={
  "TWSE_DAILY_MARKET":"TWSE_DAILY_MARKET",
  "TPEX_DAILY_MARKET":"TPEX_DAILY_MARKET",
  "MOPS_MONTHLY_REVENUE":"MOPS_MONTHLY_REVENUE",
  "TDCC_WEEKLY_OWNERSHIP":"TDCC_WEEKLY_OWNERSHIP",
  "TAIFEX_DAILY":"TAIFEX_DAILY",
  "NDC_BUSINESS_CYCLE":"NDC_BUSINESS_CYCLE",
  "CUSTOMS_TRADE":"CUSTOMS_TRADE",
  "MOEA_INDUSTRIAL_PRODUCTION":"MOEA_INDUSTRIAL_PRODUCTION"}
 for month in MONTHS:
  dataset_release_matrix[month]={}
  for spec in canonical_rules["sources"]:
   dataset=spec["dataset_id"]
   gate=source_to_gate.get(dataset)
   if gate is None:
    result={"status":"PUBLISHED_DATE_NOT_YET_VERIFIED","count_as_missing":None}
   else:
    result=official_release_classify(gate,month,now=now)
   dataset_release_matrix[month][dataset]={
     "source":spec["source"],"release_classification":result,
     "nominal_deadline":spec.get("nominal_deadline"),
     "calendar_record":spec.get("confirmed_calendar",{}).get(month),
     "receipt_evidence":"UNKNOWN_NOT_TO_BE_INFERRED_FROM_FOLDER",
     "validated_bronze_silver_gold":False,
     "historical_pit_approved":False,
     "lookup_grain":spec["grain"]}
 all_verdicts=[v["acceptance"]["status"] for one in maturity_by_month.values() for v in one.values()]
 overall=combined_state(all_verdicts,technical_error=bool(bad))
 # Downstream is not certified until schema contracts, formula DAG, PIT and
 # lineage are all checked. Observed downstream outputs remain candidates.
 downstream_verdicts={}
 for month in MONTHS:
  downstream_verdicts[month]={}
  for stage,items in (("SILVER",silver[month]),("GOLD",gold[month])):
   downstream_verdicts[month][stage]={
    name:{"status":"PARTIAL" if row.get("known_parquet_pass",0)>0 or row.get("matching_candidate_names",0)>0 else "BLOCK",
          "reason":"CANDIDATE_NOT_SCHEMA_PIT_CERTIFIED" if row.get("known_parquet_pass",0)>0 else "MISSING_OR_UNVERIFIED_OUTPUT",
          "rmi":None} for name,row in items.items()}
 report={"schema":"JARVIS_V095_202609_11_14LANE_ACCEPTANCE_MATRIX_V1",
   "run_id":run,"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "expected_lanes":14,"observed_lanes":len(entries),"missing_or_failed_receipts":bad,
   "months":list(MONTHS),"bronze_observed_source_month_cells":source_cells,
   "bronze_expected_source_month_cells":18,
   "bronze_observed_by_month":observed,"bronze":bronze,"silver":silver,"gold":gold,
   "execution_result":"PASS" if not bad else "ERROR",
   "data_acceptance_result":overall,
   "status_legend":{"PASS":"Contract+quality+PIT+lineage certified","PARTIAL":"Some actual data present, completeness not certified","BLOCK":"Not yet due or awaiting source/formula/approval","ERROR":"Transport/parser/runtime/integrity fault"},
   "rmi_units":"Percent of verified units / expected applicable units when exact certified denominator exists; otherwise null",
   "canonical_validity_rules":{"version":canonical_rules["version"],"file":"config/v095_data_validity_system_rules.json",
    "datasets":len(canonical_rules["sources"]),"hash_sha256":sha(pathlib.Path("config/v095_data_validity_system_rules.json").read_bytes())},
   "dataset_release_matrix":dataset_release_matrix,
   "release_evidence_note":"Official expected publication timing is NOT a source record's actual first_published_at; neither source-month folder nor CI pass certifies PIT.",
   "rmi_by_source_month":maturity_by_month,
   "downstream_acceptance_by_month":downstream_verdicts,
   "rmi_overall":None,
   "release_date_monitor_note":"NOT_YET_DUE excluded from overdue denominator; early company releases must be scanned; official receipt required for PIT",
   "bronze_completeness_ge_98_percent":"NOT_CERTIFIED",
   "bronze_correctness_ge_98_percent":"NOT_CERTIFIED",
   "silver_full_dataset_contracts":"NOT_CERTIFIED",
   "gold_month_applicable_indicator_formulas":"NOT_CERTIFIED",
   "historical_pit":"NOT_CERTIFIED",
   "source_v093_official_finmind_priority":"REQUIRED_REUSE_EXISTING_NOT_VERIFIED_UNIVERSE",
   "future_information_leakage":"REJECT_UNTIL_AVAILABLE_AT_PROVEN",
   "all_three_months_complete_and_correct":False,
   "data_release":"BLOCKED",
   "meaning":"14 successful Jobs != full validated market dataset; source-month existence is not dataset coverage"}
 raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
 (OUT/"202609_11_matrix.json").write_bytes(raw)
 s=service();name="JARVIS_V095_202609_11_14LANE_ACCEPTANCE_"+run+".json"
 f=s.files().create(body={"name":name,"parents":[PARENT]},
  media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json"),fields="id").execute()
 check=s.files().get_media(fileId=f["id"]).execute()
 if sha(check)!=sha(raw):raise ValueError("AGGREGATE_READBACK_SHA_MISMATCH")
 print(json.dumps({"run_id":run,"workers_with_receipts":len(entries),"expected":14,
  "missing_receipts":len(bad),"bronze_source_month_observed":source_cells,
  "source_month_expected":18,"by_month":observed,"formal_data_release":"BLOCKED","execution_result":"PASS" if not bad else "ERROR","data_acceptance_result":overall,
  "rmi_by_month":{m:{s:v["acceptance"]["status"] for s,v in mrows.items()} for m,mrows in maturity_by_month.items()},
  "drive_report_id":f["id"]},ensure_ascii=False),flush=True)
 if bad:raise RuntimeError("INCOMPLETE_14LANE_AUDIT_EVIDENCE")
if __name__=="__main__":main()
