"""Durable gap ledger and owner-routed repair tasks; never downloads market data.

All mutations use compare-and-swap. Owner receipts, not task submission, close gaps.
Live stage integration is deliberately separate from this tested queue engine.
"""
import argparse
import base64
import calendar
import copy
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

OWNERS={'RAW','QA1','PRICE','FINANCIAL','CHIP'}
RULES={
    'RAW_MISSING':('RAW',{'hash_readback_ok','source_ok','date_ok','security_ok'}),
    'RAW_CORRUPT':('RAW',{'hash_readback_ok','source_ok','date_ok','security_ok'}),
    'BASIC_QA':('QA1',{'hash_readback_ok','source_ok','date_ok','security_ok','schema_ok'}),
    'PARSER_MAPPING':(None,{'hash_readback_ok','parser_ok','date_ok','security_ok'}),
    'NUMERIC_CONFLICT':(None,{'numeric_ok','unit_ok','independent_comparison_ok'}),
    'PIT_UNKNOWN':(None,{'pit_ok','publication_evidence_ok'}),
}

class Conflict(RuntimeError):pass
class StaleClaim(RuntimeError):pass

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def checked_hash(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        raise ValueError('INVALID_SHA256')
    return value

def empty():
    return {'schema_version':1,'revision':0,'gaps':{},'tasks':{},'attempts':{},'approved_versions':{},'import_holds':{}}

def validate(doc):
    if doc.get('schema_version')!=1 or any(not isinstance(doc.get(k),dict) for k in ('gaps','tasks','attempts','approved_versions')):
        raise ValueError('INVALID_LEDGER_SCHEMA')
    return doc

def checked_unit(unit):
    fields=('source','market','dataset','security_id','period_start','period_end','native_unit_id')
    if set(unit)!=set(fields) or any(not isinstance(unit[k],str) or not unit[k] for k in fields):
        raise ValueError('INCOMPLETE_UNIT_IDENTITY')
    if any(len(v)>120 or '\n' in v or '/' in v for v in unit.values()):raise ValueError('UNSAFE_UNIT_IDENTITY')
    a,b=(dt.date.fromisoformat(unit[k]) for k in ('period_start','period_end'))
    if a>b or a<dt.date(2000,1,1) or b>dt.date(2026,10,31):raise ValueError('UNIT_OUTSIDE_AUTHORIZED_SCOPE')
    return copy.deepcopy(unit)


def receipt_unit(row):
    source=row['source'];period=row['period']
    if source not in ('TWSE','TPEx','MOPS','FinMind'):raise ValueError('UNSUPPORTED_RECEIPT_SOURCE')
    if re.fullmatch(r'\d{4}-\d{2}',period):
        y,m=map(int,period.split('-'));a=period+'-01';b=period+f'-{calendar.monthrange(y,m)[1]:02d}'
    elif re.fullmatch(r'\d{4}-\d{2}-\d{2}',period):a=b=period
    else:raise ValueError('UNPROVEN_RECEIPT_PERIOD')
    return checked_unit(dict(source=source,market={'TWSE':'TSE','TPEx':'OTC'}.get(source,'UNKNOWN'),
        dataset=row['category'],security_id='ALL_MARKET',period_start=a,period_end=b,native_unit_id=row['unit_id']))

class FileStore:
    """Local atomic CAS; cross-process lock protects replacement, not owner work."""
    def __init__(self,path):self.path=Path(path)
    def read(self):
        if not self.path.exists():return None,empty()
        raw=self.path.read_bytes()
        return hashlib.sha256(raw).hexdigest(),validate(json.loads(raw))
    def cas(self,expected,doc):
        import fcntl
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with open(str(self.path)+'.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            actual,_=self.read()
            if actual!=expected:return False
            validate(doc)
            fd,name=tempfile.mkstemp(dir=self.path.parent,prefix=self.path.name+'.')
            try:
                with os.fdopen(fd,'wb') as f:
                    f.write(json.dumps(doc,sort_keys=True,separators=(',',':')).encode());f.flush();os.fsync(f.fileno())
                os.replace(name,self.path)
                directory=os.open(self.path.parent,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
            finally:
                if os.path.exists(name):os.unlink(name)
            return True

class GitHubStore:
    """Contents API CAS on a dedicated ledger file; never uses live worker leases."""
    def __init__(self,repo,path,token):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo) or not re.fullmatch(r'[\w./-]+',path) or '..' in path.split('/'):
            raise ValueError('INVALID_STORE_PATH')
        if not re.fullmatch(r'\.github/live-state/stage06-[A-Za-z0-9_-]+\.json',path):raise ValueError('DEDICATED_STAGE06_STORE_REQUIRED')
        self.url='https://api.github.com/repos/'+repo+'/contents/'+path
        self.headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'}
    def read(self):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url,headers=self.headers),timeout=30) as r:data=json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404:return None,empty()
            raise
        return data['sha'],validate(json.loads(base64.b64decode(data['content'])))
    def cas(self,expected,doc):
        raw=json.dumps(validate(doc),sort_keys=True,separators=(',',':')).encode()
        if len(raw)>800_000:raise ValueError('LEDGER_SHARD_REQUIRED')
        body={'message':'stage06: durable gap and repair task transaction',
              'content':base64.b64encode(raw).decode()}
        if expected is not None:body['sha']=expected
        req=urllib.request.Request(self.url,data=json.dumps(body).encode(),headers=self.headers,method='PUT')
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.status in (200,201)
        except urllib.error.HTTPError as e:
            if e.code==409:return False
            if e.code==422:
                actual,_=self.read()
                if actual!=expected:return False
            raise

class Ledger:
    def __init__(self,store,clock=time.time):self.store=store;self.clock=clock
    def snapshot(self):return self.store.read()[1]
    def transaction(self,fn):
        now=int(self.clock())
        attempts=getattr(self.store,'transaction_attempts',16)
        for attempt in range(attempts):
            etag,state=self.store.read();before=digest(state)
            result=fn(state,now)
            if digest(state)==before:return copy.deepcopy(result)
            state['revision']+=1
            if self.store.cas(etag,state):return copy.deepcopy(result)
            backoff=getattr(self.store,'conflict_backoff',None)
            if attempt<attempts-1 and backoff is not None:backoff(attempt)
        raise Conflict('CAS_RETRY_EXHAUSTED')
    def observe(self,unit,kind,owner,evidence_sha256,reason_code,prior_attempts=None,expected_evidence_sha256=None,attempt_evidence_sha256=None):
        unit=checked_unit(unit);checked_hash(evidence_sha256)
        if kind not in RULES or owner not in OWNERS or RULES[kind][0] not in (None,owner):raise ValueError('INVALID_GAP_OWNER')
        if kind=='PARSER_MAPPING' and owner not in {'PRICE','FINANCIAL','CHIP'}:raise ValueError('INVALID_PARSER_OWNER')
        if not re.fullmatch('[A-Z0-9_]{1,100}',reason_code):raise ValueError('INVALID_REASON_CODE')
        if prior_attempts is not None:
            if type(prior_attempts) is not int or prior_attempts<0:raise ValueError('INVALID_ATTEMPTS')
            checked_hash(attempt_evidence_sha256)
        if expected_evidence_sha256 is not None:checked_hash(expected_evidence_sha256)
        gap_id=digest([unit,kind,owner,evidence_sha256])
        def apply(s,now):
            aid=digest(unit)
            attempts=s['attempts'].setdefault(aid,{'used':0,'known':False,'requests':{}})
            if prior_attempts is not None:
                attempts.update(used=max(attempts['used'],prior_attempts),known=True,attempt_evidence_sha256=attempt_evidence_sha256)
            if gap_id not in s['gaps']:
                s['gaps'][gap_id]={'gap_id':gap_id,'unit':unit,'kind':kind,'owner':owner,'evidence_sha256':evidence_sha256,
                    'expected_evidence_sha256':expected_evidence_sha256,'reason_code':reason_code,'status':'OPEN',
                    'first_seen':now,'attempt_key':aid,'task_ids':[],'resolution':None}
            gap=s['gaps'][gap_id]
            if expected_evidence_sha256 is not None:
                if gap['expected_evidence_sha256'] not in (None,expected_evidence_sha256):raise ValueError('EXPECTED_EVIDENCE_CONFLICT')
                gap['expected_evidence_sha256']=expected_evidence_sha256
            return gap
        return self.transaction(apply)

    def reconcile_identity(self,hold_id,original_receipt,registry,registry_evidence_sha256):
        """Resolve identity only by exact receipt and unique native id+RAW hash."""
        checked_hash(registry_evidence_sha256)
        def apply(s,now):
            hold=s['import_holds'][hold_id]
            if digest(original_receipt)!=hold['receipt_sha256'] or original_receipt.get('unit_id')!=hold['unit_id']:
                raise ValueError('ORIGINAL_RECEIPT_EVIDENCE_MISMATCH')
            checked_hash(original_receipt.get('raw_sha256'))
            candidates=[r for r in registry if r.get('unit_id')==hold['unit_id'] and
                r.get('sha256')==original_receipt['raw_sha256'] and r.get('status')=='SAVED_BASIC_VERIFIED']
            if len(candidates)!=1:raise ValueError('NATIVE_RECEIPT_NOT_UNIQUE')
            row=candidates[0]
            for field in ('source','category','period'):
                if original_receipt.get(field) not in (None,row.get(field)):raise ValueError('RECEIPT_IDENTITY_CONFLICT')
            unit=receipt_unit(row);owner=hold['stage']
            if owner not in ('QA1','PRICE','FINANCIAL','CHIP'):raise ValueError('INVALID_IDENTITY_OWNER')
            kind='BASIC_QA' if owner=='QA1' else 'PARSER_MAPPING'
            if 'HASH_MISMATCH' in original_receipt.get('error',''):kind='RAW_CORRUPT';owner='RAW'
            evidence=original_receipt['raw_sha256'];gid=digest([unit,kind,owner,evidence])
            if hold['status']=='IDENTITY_RECONCILED':
                if hold['gap_id']!=gid:raise ValueError('RECONCILED_IDENTITY_CONFLICT')
                return s['gaps'][gid]
            aid=digest(unit);s['attempts'].setdefault(aid,{'used':0,'known':False,'requests':{}})
            reason=next((x for x in ('NO_SECURITY_ID','NO_CONTENT_OR_FILENAME_DATE','HASH_MISMATCH') if x in original_receipt.get('error','')),'QUARANTINED_REVIEW')
            s['gaps'].setdefault(gid,dict(gap_id=gid,unit=unit,kind=kind,owner=owner,evidence_sha256=evidence,
                expected_evidence_sha256=None,reason_code=reason,status='OPEN',first_seen=now,attempt_key=aid,task_ids=[],resolution=None))
            hold.update(status='IDENTITY_RECONCILED',gap_id=gid,reconciled_at=now,
                registry_evidence_sha256=registry_evidence_sha256,native_receipt_sha256=digest(row))
            return s['gaps'][gid]
        return self.transaction(apply)

    def approve_version(self,owner,version,approval_evidence_sha256):
        if owner not in OWNERS or not re.fullmatch('[A-Za-z0-9_.-]{1,80}',version):raise ValueError('INVALID_VERSION')
        checked_hash(approval_evidence_sha256)
        def apply(s,now):
            key=owner+':'+version
            old=s['approved_versions'].get(key)
            if old and old!=approval_evidence_sha256:raise ValueError('APPROVAL_CONFLICT')
            s['approved_versions'][key]=approval_evidence_sha256
            return key
        return self.transaction(apply)
    def enqueue(self,gap_id,input_sha256,processor_version,rule_version,priority=0):
        checked_hash(input_sha256)
        if not re.fullmatch('[A-Za-z0-9_.-]{1,80}',processor_version) or not re.fullmatch('[A-Za-z0-9_.-]{1,80}',rule_version):raise ValueError('INVALID_VERSION')
        if type(priority) is not int or not 0<=priority<=10:raise ValueError('INVALID_PRIORITY')
        def apply(s,now):
            gap=s['gaps'][gap_id]
            if gap['status']=='RESOLVED':raise ValueError('GAP_ALREADY_RESOLVED')
            if gap['kind'] not in ('RAW_MISSING','RAW_CORRUPT') and input_sha256!=gap['evidence_sha256']:raise ValueError('INPUT_EVIDENCE_HASH_MISMATCH')
            if gap['kind'] in ('RAW_MISSING','RAW_CORRUPT') and not gap['expected_evidence_sha256']:
                raise ValueError('EXPECTED_UNIT_EVIDENCE_REQUIRED')
            tid=digest([gap_id,input_sha256,processor_version,rule_version])
            if tid in s['tasks']:return s['tasks'][tid]
            approved=gap['owner']+':'+processor_version in s['approved_versions']
            status='READY' if approved else 'BLOCKED_APPROVAL'
            if gap['kind'] in ('RAW_MISSING','RAW_CORRUPT'):
                attempt=s['attempts'][gap['attempt_key']]
                if not attempt['known']:status='BLOCKED_ATTEMPT_RECONCILIATION'
                elif attempt['used']>=5:status='RETRY_EXHAUSTED'
            task={'task_id':tid,'gap_id':gap_id,'owner':gap['owner'],'input_sha256':input_sha256,
                'processor_version':processor_version,'rule_version':rule_version,'priority':priority,
                'status':status,'fence':0,'claim':None,'receipt':None,'created_at':now}
            s['tasks'][tid]=task;gap['task_ids'].append(tid);gap['status']='RETRY_EXHAUSTED' if status=='RETRY_EXHAUSTED' else 'WAITING_OWNER'
            return task
        return self.transaction(apply)
    @staticmethod
    def owned(s,tid,worker,fence,now):
        t=s['tasks'][tid];claim=t.get('claim') or {}
        if t['status']!='CLAIMED' or claim.get('worker')!=worker or t['fence']!=fence or claim.get('expires_at',0)<=now:
            raise StaleClaim('STALE_OR_EXPIRED_OWNER')
        return t
    def claim(self,owner,worker,ttl=5400,processor_version=None,rule_version=None,gap_kinds=None,unit_sources=None):
        if owner not in OWNERS or not re.fullmatch('[A-Za-z0-9_./-]{1,120}',worker) or type(ttl) is not int or ttl<=0:raise ValueError('INVALID_CLAIM')
        def apply(s,now):
            choices=[]
            for t in s['tasks'].values():
                if t['owner']!=owner:continue
                g=s['gaps'][t['gap_id']]
                if g['status']=='RESOLVED' and t['status']!='DONE':
                    t.update(status='CANCELLED_SUPERSEDED',claim=None);continue
                if t['status']=='CLAIMED' and t['claim']['expires_at']<=now:
                    a=s['attempts'][g['attempt_key']]
                    unknown=any(r['task_id']==t['task_id'] and r['status']=='IN_FLIGHT' for r in a['requests'].values())
                    t.update(status='RECONCILE_REQUIRED' if unknown else 'READY',claim=None)
                    saved=[r for r in a['requests'].values() if r['task_id']==t['task_id'] and r['status']=='OBSERVED']
                    if not unknown and saved:
                        last=max(saved,key=lambda r:r['attempt'])
                        t.update(validation_only=True,recovered_output_sha256=last['response_sha256'],status='REPAIRED_PENDING_QA')
            busy={s['gaps'][t['gap_id']]['attempt_key'] for t in s['tasks'].values()
                  if t['owner']==owner and t['status'] in ('CLAIMED','RECONCILE_REQUIRED')}
            for t in s['tasks'].values():
                if t['owner']!=owner:continue
                if processor_version is not None and t['processor_version']!=processor_version:continue
                if rule_version is not None and t['rule_version']!=rule_version:continue
                if gap_kinds is not None and s['gaps'][t['gap_id']]['kind'] not in gap_kinds:continue
                if unit_sources is not None and s['gaps'][t['gap_id']]['unit']['source'] not in unit_sources:continue
                g=s['gaps'][t['gap_id']];attempts=s['attempts'][g['attempt_key']]
                if g['attempt_key'] in busy:continue
                if t['status'] in ('BLOCKED_APPROVAL','BLOCKED_ATTEMPT_RECONCILIATION'):
                    if g['kind'] in ('RAW_MISSING','RAW_CORRUPT') and not attempts['known']:continue
                    if owner+':'+t['processor_version'] in s['approved_versions']:t['status']='READY'
                if t['status']=='FAILED_OWNER' and len(t.get('failures',[]))<5:
                    t['status']='READY'
                if len(t.get('failures',[]))>=5 and t['status'] not in ('DONE','CLAIMED','RECONCILE_REQUIRED'):
                    t.update(status='RETRY_EXHAUSTED',claim=None);g['status']='RETRY_EXHAUSTED';continue
                if t['status'] in ('READY','REPAIRED_PENDING_QA'):
                    if not t.get('validation_only') and g['kind'] in ('RAW_MISSING','RAW_CORRUPT') and attempts['used']>=5:
                        t.update(status='RETRY_EXHAUSTED',claim=None);g['status']='RETRY_EXHAUSTED';continue
                    choices.append(t)
            if not choices:return None
            choices.sort(key=lambda t:(-t['priority'],-dt.date.fromisoformat(s['gaps'][t['gap_id']]['unit']['period_end']).toordinal(),t['task_id']))
            t=choices[0];t['fence']+=1;t.update(status='CLAIMED',claim={'worker':worker,'expires_at':now+ttl})
            return t
        return self.transaction(apply)
    def begin_request(self,tid,worker,fence,request_id):
        if not re.fullmatch('[A-Za-z0-9_.-]{1,100}',request_id):raise ValueError('INVALID_REQUEST_ID')
        def apply(s,now):
            t=self.owned(s,tid,worker,fence,now);g=s['gaps'][t['gap_id']]
            if g['kind'] not in ('RAW_MISSING','RAW_CORRUPT'):raise ValueError('NETWORK_DOWNLOAD_NOT_ALLOWED_FOR_TASK')
            if t.get('validation_only'):raise ValueError('SAVED_RESPONSE_MUST_BE_REUSED')
            today=dt.datetime.fromtimestamp(now,dt.timezone(dt.timedelta(hours=8))).date()
            if dt.date.fromisoformat(g['unit']['period_end'])>today:raise ValueError('FUTURE_UNIT_NOT_AVAILABLE')
            a=s['attempts'][g['attempt_key']]
            if not a['known']:raise ValueError('RECONCILE_PRIOR_ATTEMPTS_FIRST')
            if request_id in a['requests']:
                old=a['requests'][request_id]
                if old['task_id']!=tid:raise ValueError('REQUEST_ID_COLLISION')
                # Caller must never replay HTTP after a previously recorded intent.
                return {'send_allowed':False,'record':old}
            if any(r['status']=='IN_FLIGHT' for r in a['requests'].values()):raise ValueError('RECONCILE_UNKNOWN_REQUEST_FIRST')
            if a['used']>=5:
                t.update(status='RETRY_EXHAUSTED',claim=None);g['status']='RETRY_EXHAUSTED'
                return {'send_allowed':False,'reason':'RETRY_EXHAUSTED'}
            a['used']+=1;a['requests'][request_id]={'task_id':tid,'fence':fence,'status':'IN_FLIGHT','started_at':now,'attempt':a['used']}
            return {'send_allowed':True,'record':a['requests'][request_id]}
        return self.transaction(apply)
    def end_request(self,tid,worker,fence,request_id,response_sha256):
        checked_hash(response_sha256)
        def apply(s,now):
            t=self.owned(s,tid,worker,fence,now);a=s['attempts'][s['gaps'][t['gap_id']]['attempt_key']];r=a['requests'][request_id]
            if r['task_id']!=tid or r['fence']!=fence:raise StaleClaim('REQUEST_FENCE_MISMATCH')
            if r['status']=='OBSERVED' and r['response_sha256']!=response_sha256:raise ValueError('RESPONSE_HASH_CONFLICT')
            r.update(status='OBSERVED',response_sha256=response_sha256)
            return r
        return self.transaction(apply)
    def reconcile(self,tid,request_id,evidence_sha256,found_response_sha256=None):
        checked_hash(evidence_sha256)
        if found_response_sha256 is not None:checked_hash(found_response_sha256)
        def apply(s,now):
            t=s['tasks'][tid]
            if t['status']!='RECONCILE_REQUIRED':raise ValueError('TASK_NOT_AWAITING_RECONCILIATION')
            a=s['attempts'][s['gaps'][t['gap_id']]['attempt_key']];r=a['requests'][request_id]
            if r['task_id']!=tid or r['status']!='IN_FLIGHT':raise ValueError('NOT_UNKNOWN_REQUEST')
            r.update(status='FOUND_SAVED_RESPONSE' if found_response_sha256 else 'CONFIRMED_NOT_SAVED',reconciliation_evidence_sha256=evidence_sha256)
            if found_response_sha256:
                r['response_sha256']=found_response_sha256
                t.update(validation_only=True,recovered_output_sha256=found_response_sha256)
            t['status']='REPAIRED_PENDING_QA' if found_response_sha256 else ('RETRY_EXHAUSTED' if a['used']>=5 else 'READY')
            s['gaps'][t['gap_id']]['status']=t['status']
            return t
        return self.transaction(apply)
    def fail(self,tid,worker,fence,error_code,evidence_sha256,retryable=True):
        checked_hash(evidence_sha256)
        if not re.fullmatch('[A-Z0-9_]{1,100}',error_code):raise ValueError('INVALID_REASON_CODE')
        def apply(s,now):
            t=self.owned(s,tid,worker,fence,now);g=s['gaps'][t['gap_id']];a=s['attempts'][g['attempt_key']]
            if any(r['task_id']==tid and r['status']=='IN_FLIGHT' for r in a['requests'].values()):raise ValueError('UNRECONCILED_HTTP_INTENT')
            t.setdefault('failures',[]).append({'fence':fence,'code':error_code,'evidence_sha256':evidence_sha256,'at':now})
            raw=g['kind'] in ('RAW_MISSING','RAW_CORRUPT')
            t.update(status=('RETRY_EXHAUSTED' if a['used']>=5 else 'READY') if raw else 'FAILED_OWNER',claim=None)
            if not raw and len(t['failures'])>=5:t['status']='RETRY_EXHAUSTED'
            if raw and not retryable:t['status']='FAILED_PERMANENT'
            t.pop('validation_only',None);t.pop('recovered_output_sha256',None)
            g['status']='RETRY_EXHAUSTED' if t['status']=='RETRY_EXHAUSTED' else 'OPEN'
            return t
        return self.transaction(apply)
    def reuse_saved_raw(self,tid,response_sha256,evidence_sha256):
        checked_hash(response_sha256);checked_hash(evidence_sha256)
        def apply(s,now):
            t=s['tasks'][tid];g=s['gaps'][t['gap_id']];a=s['attempts'][g['attempt_key']]
            if t['owner']!='RAW' or g['kind'] not in ('RAW_MISSING','RAW_CORRUPT'):raise ValueError('NOT_RAW_REPAIR')
            if t['status'] in ('CLAIMED','RECONCILE_REQUIRED','DONE'):raise ValueError('TASK_NOT_AVAILABLE_FOR_NATIVE_REUSE')
            if any(r['status']=='IN_FLIGHT' for r in a['requests'].values()):raise ValueError('UNRECONCILED_HTTP_INTENT')
            if t.get('recovered_output_sha256') not in (None,response_sha256):raise ValueError('SAVED_RESPONSE_CONFLICT')
            t.update(validation_only=True,recovered_output_sha256=response_sha256,
                native_reuse_evidence={'sha256':response_sha256,'evidence_sha256':evidence_sha256})
            t['status']='REPAIRED_PENDING_QA' if 'RAW:'+t['processor_version'] in s['approved_versions'] else 'BLOCKED_APPROVAL'
            return t
        return self.transaction(apply)
    def release(self,tid,worker,fence,reason='BUDGET_DEFERRED'):
        if not re.fullmatch('[A-Z0-9_]{1,100}',reason):raise ValueError('INVALID_REASON_CODE')
        def apply(s,now):
            t=self.owned(s,tid,worker,fence,now);g=s['gaps'][t['gap_id']];a=s['attempts'][g['attempt_key']]
            if any(r['task_id']==tid and r['status']=='IN_FLIGHT' for r in a['requests'].values()):raise ValueError('UNRECONCILED_HTTP_INTENT')
            t.update(status='REPAIRED_PENDING_QA' if t.get('validation_only') else 'READY',claim=None)
            t.setdefault('deferrals',[]).append(dict(reason=reason,at=now,fence=fence))
            return t
        return self.transaction(apply)
    def complete(self,tid,worker,fence,receipt):
        checked_hash(receipt.get('output_sha256'));checked_hash(receipt.get('validation_evidence_sha256'))
        def apply(s,now):
            t=s['tasks'][tid];g=s['gaps'][t['gap_id']]
            if t['status']=='DONE':
                if t['receipt']==receipt:return t
                raise ValueError('COMPLETED_RECEIPT_CONFLICT')
            self.owned(s,tid,worker,fence,now)
            if any(receipt.get(k)!=v for k,v in {'task_id':tid,'owner':t['owner'],'fence':fence,'input_sha256':t['input_sha256'],'processor_version':t['processor_version']}.items()):raise ValueError('RECEIPT_IDENTITY_MISMATCH')
            a=s['attempts'][g['attempt_key']]
            if any(r['task_id']==tid and r['status']=='IN_FLIGHT' for r in a['requests'].values()):raise ValueError('UNRECONCILED_HTTP_INTENT')
            if not all(receipt.get('checks',{}).get(k) is True for k in RULES[g['kind']][1]):raise ValueError('GAP_SPECIFIC_VALIDATION_REQUIRED')
            if g['kind'] in ('RAW_MISSING','RAW_CORRUPT') and not (t.get('native_reuse_evidence',{}).get('sha256')==receipt['output_sha256'] or any(r['task_id']==tid and r['status'] in ('OBSERVED','FOUND_SAVED_RESPONSE') and r.get('response_sha256')==receipt['output_sha256'] for r in a['requests'].values())):raise ValueError('SAVED_RAW_RESPONSE_EVIDENCE_REQUIRED')
            if t.get('recovered_output_sha256') and receipt['output_sha256']!=t['recovered_output_sha256']:raise ValueError('RECOVERED_RESPONSE_HASH_MISMATCH')
            t.update(status='DONE',claim=None,receipt=copy.deepcopy(receipt));g.update(status='RESOLVED',resolution={'task_id':tid,'output_sha256':receipt['output_sha256'],'validation_evidence_sha256':receipt['validation_evidence_sha256'],'resolved_at':now})
            return t
        return self.transaction(apply)

def import_quarantine(ledger,stage,month_state,processor_version=None,rule_version='STAGE06_RULES_V1'):
    """Import existing isolated receipts, not inferred missing market data."""
    count=0
    for row_key,row in month_state.get('units',{}).items():
        if row.get('status')!='QUARANTINED':continue
        raw_hash=row.get('raw_sha256')
        if not raw_hash or not row.get('period') or not row.get('source') or not row.get('category'):
            def hold(s,now):
                hid=digest([stage,month_state.get('month'),row_key,digest(row)])
                s.setdefault('import_holds',{}).setdefault(hid,{'hold_id':hid,'stage':stage,'receipt_sha256':digest(row),'unit_id':row.get('unit_id'),'status':'IDENTITY_RECONCILIATION_REQUIRED','reason':'MISSING_HASH_OR_SOURCE_DATASET_PERIOD','first_seen':now})
            ledger.transaction(hold)
            continue
        period=row.get('period','')
        if re.fullmatch(r'\d{4}-\d{2}',period):
            y,m=map(int,period.split('-'));a=period+'-01';b=period+f'-{calendar.monthrange(y,m)[1]:02d}'
        elif re.fullmatch(r'\d{4}-\d{2}-\d{2}',period):a=b=period
        else:continue
        source=row.get('source','UNKNOWN');category=row.get('category','UNKNOWN')
        market='TSE' if source=='TWSE' else ('OTC' if source=='TPEx' else 'UNKNOWN')
        unit={'source':source,'market':market,'dataset':category,'security_id':'ALL_MARKET',
              'period_start':a,'period_end':b,'native_unit_id':row.get('unit_id') or digest([source,category,period])}
        error=row.get('error','')
        reason=next((x for x in ('NO_SECURITY_ID','NO_CONTENT_OR_FILENAME_DATE','HASH_MISMATCH','NO_PARSED_NUMERIC_CELLS') if x in error),'QUARANTINED_REVIEW')
        kind='RAW_CORRUPT' if 'HASH_MISMATCH' in error else ('BASIC_QA' if stage=='QA1' else 'PARSER_MAPPING')
        owner='RAW' if kind=='RAW_CORRUPT' else stage
        gap=ledger.observe(unit,kind,owner,raw_hash,reason)
        # A transform receipt is not evidence of the RAW HTTP attempt count.
        if processor_version and kind not in ('RAW_CORRUPT','RAW_MISSING'):
            ledger.enqueue(gap['gap_id'],raw_hash,processor_version,rule_version)
        count+=1
    return count

def summary(state):
    from collections import Counter
    return {'gaps':len(state['gaps']),'gap_statuses':dict(Counter(x['status'] for x in state['gaps'].values())),
            'tasks':len(state['tasks']),'task_statuses':dict(Counter(x['status'] for x in state['tasks'].values())),
            'identity_holds':sum(h['status']!='IDENTITY_RECONCILED' for h in state.get('import_holds',{}).values()),
            'identities_reconciled':sum(h['status']=='IDENTITY_RECONCILED' for h in state.get('import_holds',{}).values()),
            'source_downloads_performed':0,'numeric_verified':False,'pit_verified':False,'owner_runtime_integrated':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--ledger',required=True);p.add_argument('--import-quarantine');p.add_argument('--stage',choices=sorted(OWNERS));p.add_argument('--processor-version');a=p.parse_args()
    ledger=Ledger(FileStore(a.ledger))
    if a.import_quarantine:
        if not a.stage:p.error('--stage is required for import')
        import_quarantine(ledger,a.stage,json.loads(Path(a.import_quarantine).read_text()),processor_version=a.processor_version)
    print(json.dumps(summary(ledger.snapshot()),sort_keys=True))

if __name__=='__main__':main()
