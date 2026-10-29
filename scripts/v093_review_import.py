"""Atomic legacy review import; no network or source download authorization."""
import copy,hashlib,json

def install(coordinator,review,assignments,generation):
 source=coordinator.source;rows=review['tasks']
 if not isinstance(generation,str) or not generation or set(rows)!=set(assignments):raise ValueError('IMPORT_MANIFEST')
 prepared={}
 for key,row in sorted(rows.items()):
  count=row.get('attempts');versions=row.get('provenance')
  if row.get('source')!=source or row.get('task_key')!=key or type(count) is not int or count<0 or not versions:raise ValueError('IMPORT_IDENTITY_OR_ATTEMPTS')
  if assignments[key] not in ('ASC','DESC') or source in ('NDC','FinMind') and assignments[key]!='DESC':raise ValueError('IMPORT_SLOT')
  periods={v.get('period') for v in versions}
  if len(periods)!=1:raise ValueError('IMPORT_PERIOD_CONFLICT')
  period=next(iter(periods))
  import datetime
  if not isinstance(period,str):raise ValueError('IMPORT_PERIOD')
  datetime.date.fromisoformat(period+'-01' if len(period)==7 else period)
  if any(v.get('source',source)!=source or v.get('task_key',key)!=key or type(v.get('attempts',count)) is not int or not 0<=v.get('attempts',count)<=count for v in versions):raise ValueError('IMPORT_PROVENANCE')
  # Initial import stays isolated until source adapters validate applicability,
  # retained receipt bindings and native semantics. No READY promotion here.
  status='RECONCILE' if row.get('action')=='RECONCILE_INTERRUPTED_REQUEST' else 'CONTENT_BLOCKED' if row.get('action')=='VERSION_CONFLICT_REVIEW' else 'BLOCKED' if count>=4 else 'APPLICABILITY_HOLD'
  prepared[key]=dict(definition=dict(source=source,key=key,slot=assignments[key],period=period),status=status,attempts=count,fence=0,owner=None,legacy_review=copy.deepcopy(row),migration_generation=generation,download_authorized=False,numeric_verified=False,pit_verified=False,full_acceptance=False)
 digest=hashlib.sha256(json.dumps(prepared,sort_keys=True).encode()).hexdigest()
 def change(state):
  imports=state.setdefault('legacy_imports',{})
  if generation in imports:
   if imports[generation]!=digest:raise ValueError('IMPORT_GENERATION_CONFLICT')
   return False
  if set(prepared)&set(state['tasks']):raise ValueError('IMPORT_EXISTING_TASK_RECONCILIATION_REQUIRED')
  state['tasks'].update(copy.deepcopy(prepared));imports[generation]=digest
  return True
 return coordinator.update(change)
