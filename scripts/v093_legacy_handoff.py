"""Normalize frozen native ledgers without promoting old QA flags to acceptance."""
import datetime as dt,hashlib,json,re
SOURCES={'TWSE','TPEx','MOPS','TDCC','TAIFEX','NDC','FinMind'}
BUCKETS=('units','financial_units','receipts','history_receipts','supplement_receipts','finmind_units')
def normalize(document,path,default_source=None,origin=None):
 rows=[];issues=[]
 match=re.search(r'(?:^|/)(20\d\d-\d\d)(?:/|$)',path)
 month=match.group(1) if match else None
 for bucket in BUCKETS:
  entries=document.get(bucket,{})
  if not isinstance(entries,dict):issues.append(dict(reason='BUCKET_SCHEMA',bucket=bucket));continue
  for key,entry in entries.items():
   if not isinstance(entry,dict):issues.append(dict(reason='RECEIPT_SCHEMA',key=key));continue
   if entry.get('stage') in ('QA1','PRICE','FINANCIAL','CHIP') and entry.get('raw_sha256'):
    issues.append(dict(reason='EXCLUDED_DERIVED_RECORD',key=key));continue
   source='FinMind' if bucket=='finmind_units' else entry.get('source',default_source)
   if source not in SOURCES:issues.append(dict(reason='SOURCE_UNKNOWN',key=key));continue
   period=entry.get('period') or entry.get('start_date') or entry.get('request',{}).get('start') or entry.get('date') or (key if re.match(r'^20\d\d-\d\d$',key) else None) or month
   # TDCC HISTORY files carry the date in each native key, not a month field.
   if not period and re.match(r'^20\d{6}\|',key):period=key[:4]+'-'+key[4:6]+'-'+key[6:8]
   if not period and re.match(r'^HISTORY_20\d{6}',path.rsplit('/',1)[-1]):
    date=path.rsplit('/',1)[-1][8:16];period=date[:4]+'-'+date[4:6]+'-'+date[6:8]
   if isinstance(period,str) and re.fullmatch(r'20\d{6}',period):period=period[:4]+'-'+period[4:6]+'-'+period[6:8]
   period_basis='CONTENT_OR_NATIVE_REQUEST'
   capture=re.match(r'^(20\d\d-\d\d-\d\d)\|/v1/opendata/',key) if source=='TDCC' else None
   if capture:
    # Snapshot task identity uses capture day; never pretend it is historical content coverage.
    period=capture.group(1);period_basis='SNAPSHOT_CAPTURE_DATE_ONLY'
   # Snapshot receipt may omit period but retains a validated content span.
   if not period:period=(entry.get('content_period') or {}).get('min')
   if not isinstance(period,str) or not re.match(r'^20\d\d-\d\d',period):
    issues.append(dict(reason='PERIOD_UNPROVEN',source=source,key=key));continue
   try:dt.date.fromisoformat(period+'-01' if len(period)==7 else period)
   except ValueError:issues.append(dict(reason='PERIOD_INVALID',source=source,key=key));continue
   scope_month=entry.get('month') or month or period[:7]
   unit=entry.get('unit_id',key)
   task_key=source+'|'+scope_month+'|'+str(unit)
   attempts=entry.get('attempts',0)
   if type(attempts) is not int or attempts<0:
    issues.append(dict(reason='INVALID_ATTEMPTS',source=source,key=key));continue
   rows.append(dict(source=source,task_key=task_key,legacy_task_id=hashlib.sha256(task_key.encode()).hexdigest()[:20],
    legacy_unit_id=str(unit),legacy_bucket=bucket,ledger_path=path,ledger_origin=origin,period=period,month=scope_month,
    status=entry.get('status','UNKNOWN'),attempts=attempts,period_basis=period_basis,content_period=entry.get('content_period'),bytes=entry.get('bytes'),raw_reference=entry.get('evidence_file') or entry.get('file_id'),
    sha256=entry.get('sha256'),archive_sha256=entry.get('archive_sha256'),
    retry_after_epoch=entry.get('retry_after_epoch',entry.get('next_retry_at')),request_phase=entry.get('request_phase'),
    prior_numeric_claim=entry.get('numeric_verified'),prior_pit_claim=entry.get('pit_verified'),
    numeric_verified=False,pit_verified=False,full_acceptance=False))
 return rows,issues

def inspect(rows):
 """All records imported to review queues; no source request is authorized here."""
 grouped={}
 for row in rows:grouped.setdefault(row['task_key'],[]).append(row)
 result={};conflicts=[]
 for key,versions in sorted(grouped.items()):
  digests={r['sha256'] for r in versions if r.get('raw_reference') and r.get('sha256')}
  attempts=max(r['attempts'] for r in versions)
  statuses={r['status'] for r in versions}
  if len(digests)>1:action='VERSION_CONFLICT_REVIEW';conflicts.append(key)
  elif any(r.get('raw_reference') for r in versions):action='VERIFY_RETAINED_RAW_FIRST'
  elif statuses & {'REQUEST_INTENT','FINMIND_REQUEST_INTENT','RAW_SAVED','PROCESSING'}:action='RECONCILE_INTERRUPTED_REQUEST'
  elif attempts>=4:action='RETRY_EXHAUSTED_REVIEW'
  else:action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE'
  result[key]=dict(task_key=key,source=versions[0]['source'],attempts=attempts,action=action,
   retry_budget_reset=False,provenance=versions,full_acceptance=False,download_authorized=False)
 return dict(schema='JARVIS_LEGACY_HANDOFF_REVIEW_V1',tasks=result,unique_tasks=len(result),
  version_conflicts=conflicts,market_requests=0,production_writes=0,ready_for_production_cutover=False)
