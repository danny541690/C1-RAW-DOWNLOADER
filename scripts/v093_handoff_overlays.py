"""Pinned later-QA outcomes overlay frozen reviews without resetting attempts.

Only actually verified missing results may become retained check contracts.
Held outcomes remain held; unrelated QA fixtures cannot enter the campaign.
"""
import copy,json,re
from pathlib import Path
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_adapters import NativeAdapter

def apply_task(reviews,source,key,task,pin,resolved_reference=None):
 if key not in reviews[source] or task.get('definition',{}).get('key')!=key or task['definition'].get('source')!=source:raise ValueError('OVERLAY_TASK_SCOPE')
 old=reviews[source][key];attempts=task.get('attempts')
 if type(attempts) is not int or attempts<old['attempts']:raise ValueError('OVERLAY_ATTEMPTS_CANNOT_DECREASE')
 item=copy.deepcopy(old);item['attempts']=attempts;item.setdefault('handoff_overlays',[]).append(dict(pin,status=task['status'],attempts=attempts));period=task['definition']['period']
 contract=None
 if task['status']=='RAW_BASIC_VERIFIED':
  sha=task.get('raw_sha256');ref=task.get('raw_reference') or resolved_reference
  if not isinstance(ref,str) or not re.fullmatch('[0-9a-f]{64}',sha or '') or task.get('save_intent',{}).get('sha256')!=sha:raise ValueError('OVERLAY_VERIFIED_RECEIPT_MISSING')
  # Do not resolve old version disputes using a new generic basic flag.
  if old['action']=='VERSION_CONFLICT_REVIEW' or {v.get('period') for v in old['provenance']}!={period}:raise ValueError('OVERLAY_UNRESOLVED_VERSION_OR_PERIOD')
  old_shas={v.get('sha256') for v in old['provenance'] if v.get('raw_reference') and v.get('sha256')}
  if old_shas and old_shas!={sha}:raise ValueError('OVERLAY_CANNOT_SILENTLY_REPLACE_OLD_RAW')
  contract=copy.deepcopy(task.get('execution_contract') or {})
  if not contract and source=='TDCC':
   unit=key.rsplit('|',2);date,code=unit[-2:]
   if not re.fullmatch(r'20\d{6}',date) or not re.fullmatch('[0-9A-Za-z]{4,8}',code):raise ValueError('OVERLAY_TDCC_NATIVE_IDENTITY')
   contract=dict(date=date,code=code)
  contract.update(source=source,key=key,period=period,mode='RETAINED',reference=ref,sha256=sha)
  for name in ('missing_evidence','repair_evidence'):contract.pop(name,None)
  item['provenance'].append(dict(source=source,task_key=key,period=period,raw_reference=ref,sha256=sha,status='RAW_BASIC_VERIFIED',attempts=attempts,ledger_origin=dict(pin),numeric_verified=False,pit_verified=False,full_acceptance=False))
  item['action']='VERIFY_RETAINED_RAW_FIRST'
  row=dict(definition=dict(source=source,key=key,period=period,slot='DESC'),attempts=attempts,legacy_review=item,execution_contract=contract)
  NativeAdapter(None,None,dict(source=source,key=key),row)
 elif task['status'] in ('APPLICABILITY_HOLD','CONTENT_BLOCKED','SOURCE_HOLD','BLOCKED','RECONCILE','REQUEST_INTENT','RETRY_WAIT'):
  item['action']='LATER_QA_'+task['status'];item['later_qa_status']=task['status']
 else:raise ValueError('OVERLAY_STATUS_NOT_REVIEWED')
 reviews[source][key]=item
 return contract

def apply_manifest(root,reviews,path,drive):
 doc=json.loads(Path(path).read_text());contracts={};held=set();events=[]
 if doc.get('schema')!='JARVIS_PINNED_HANDOFF_OVERLAYS_V1':raise ValueError('OVERLAY_MANIFEST_SCHEMA')
 for entry in doc['states']:
  source=entry['source'];prefix=entry['prefix'];expected=entry['commit']
  if not prefix.startswith('jarvis-source-preflight/') or not re.fullmatch('[0-9a-f]{40}',expected):raise ValueError('OVERLAY_PIN_SCOPE')
  store=GitCAS(root,prefix);commit,state=store.read(source)
  if commit!=expected or not state:raise ValueError('OVERLAY_PIN_NOT_LATEST_REFRESH_REQUIRED')
  for key,task in state['tasks'].items():
   resolved=entry.get('resolved_references',{}).get(key)
   case=apply_task(reviews,source,key,task,dict(prefix=prefix,commit=commit),resolved)
   if case:
    # Re-read the actual later QA RAW before promoting a frozen missing entry.
    row=dict(definition=dict(source=source,key=key,period=case['period'],slot='DESC'),attempts=reviews[source][key]['attempts'],legacy_review=reviews[source][key],execution_contract=case)
    adapter=NativeAdapter(None,drive,dict(source=source,key=key),row);raw=adapter.read(case['reference'])
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=case['sha256']:raise ValueError('OVERLAY_COLD_RAW_SHA')
    adapter.validate(raw);contracts[source,key]=case;held.discard((source,key))
   else:held.add((source,key));contracts.pop((source,key),None)
   events.append(dict(source=source,key=key,status=task['status'],attempts=task['attempts'],contract_retained=bool(case),pin=commit))
  if store.remote_head(source)!=expected:raise ValueError('OVERLAY_CHANGED_DURING_READ')
 return contracts,held,events
