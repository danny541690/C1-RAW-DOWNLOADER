"""Read-only audit inventory; never certifies coverage or publishes production data."""
import collections, datetime as dt, hashlib, json, time
from scripts.v093_standard_r1 import Drive, service

QA='10_k6r3pRGKYUp5YbyD3UA1oWw6DngHlO'
OPS='1Hv9aR_8SwAEK3o3Bl-5xY2mFjQFV31jA'
NAME='AUDIT_BACKLOG_V1.json'
R3='NATIVE_R3_20261020_1'
R4='NATIVE_R4_20261020_1'
SOURCES=('TWSE','TPEx','MOPS','FinMind')
BLOCKERS=['SOURCE_FIELD_UNIT_CONTRACT','HISTORICAL_UNIVERSE_AND_CALENDAR',
          'CORPORATE_ACTION_BASIS','POINT_IN_TIME_AND_REVISIONS',
          'INDEPENDENT_OFFICIAL_SOURCE_GOLDEN','END_TO_END_RELEASE_ACCEPTANCE']

def report_specs(period):
    if period.startswith('2024-') or period=='2025-07':
        return [(f'{period}_{R4}_AUDIT.json',SOURCES)]
    return [(f'{period}_{R3}_AUDIT.json',('TWSE','TPEx')),
            (f'{period}_{R4}_MOPS_FinMind_AUDIT.json',('MOPS','FinMind'))]

def summarize(period, documents):
    result={'period':period,'approved':False,'coverage':'NOT_VERIFIED',
            'production_blockers':BLOCKERS,'reports':[],'sources':{}}
    for name,scope in report_specs(period):
        raw=documents.get(name)
        if raw is None:
            for source in scope:result['sources'][source]={'status':'WAITING_FOR_AUDIT_REPORT'}
            continue
        r=json.loads(raw)
        if r.get('period')!=period:raise ValueError('AUDIT_PERIOD_MISMATCH')
        if r.get('version') not in (R3,R4):raise ValueError('AUDIT_VERSION_MISMATCH')
        if not set(scope).issubset(set(r.get('source_scope',SOURCES))):raise ValueError('AUDIT_SCOPE_MISMATCH')
        result['reports'].append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),
                                  'status':r.get('status'),'updated_at':r.get('updated_at')})
        entries=r.get('archives',[])+r.get('standalone_files',[])
        for source in scope:
            es=[e for e in entries if e.get('source')==source]
            issues=[];reasons=collections.Counter()
            for e in es:
                for member in e.get('members',[]):
                    if member.get('status') in ('UNRESOLVED','QUARANTINED'):
                        reasons.update(member.get('counts',{}))
                        issues.append({'input':e.get('name'),'member':member.get('member'),
                                       'status':member.get('status'),'reason':member.get('reason'),
                                       'counts':member.get('counts',{})})
            result['sources'][source]={
                'status':'REVIEW_REQUIRED' if r.get('status')=='STAGING_NOT_APPROVED' else 'WAITING_FOR_STABLE_CONVERSION',
                'missing_source':source in r.get('sources_missing',[]) or not es,
                'inputs':len(es),'staged_cells':sum(e.get('cells',0) for e in es),
                'input_errors':[{'input':e.get('name'),'reason':e.get('reason') or e.get('error')} for e in es if e.get('status')=='INPUT_ERROR'],
                'no_output_inputs':[e.get('name') for e in es if e.get('status')=='NO_STAGED_OUTPUT'],
                'ohlc_violations':sum(e.get('checks',{}).get('OHLC_VIOLATIONS',0) for e in es),
                'unresolved_or_quarantined':issues,'reason_counts':dict(reasons),
                'interpretation':'Unresolved members require classification; they are not proven missing market records.'}
    return result

def main(minutes=12):
    d=Drive(service());raw=d.read(OPS,NAME)
    state=json.loads(raw) if raw else {'version':'AUDIT_BACKLOG_V1','next_index':0,'months':{}}
    if state.get('version')!='AUDIT_BACKLOG_V1':raise ValueError('BACKLOG_VERSION_MISMATCH')
    periods=[f'2025-{m:02d}' for m in range(1,13)]+[f'2026-{m:02d}' for m in range(1,11)]+[f'2024-{m:02d}' for m in range(12,0,-1)]
    deadline=time.monotonic()+minutes*60;processed=0
    while processed<len(periods) and time.monotonic()<deadline:
        index=state['next_index'];period=periods[index]
        documents={name:d.read(QA,name) for name,_ in report_specs(period)}
        state['months'][period]=summarize(period,documents)
        state.update(next_index=(index+1)%len(periods),updated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                     approved=False,production_ready=False,status='INVENTORY_ONLY_NOT_ACCEPTANCE',
                     total_months=len(periods),production_blockers=BLOCKERS)
        d.put(OPS,NAME,json.dumps(state,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
        processed+=1
        print(json.dumps({'period':period,'status':'AUDIT_BACKLOG_SAVED','approved':False}),flush=True)
    print(json.dumps({'months_refreshed':processed,'months_in_inventory':len(state['months']),'next_index':state['next_index'],'approved':False}),flush=True)

if __name__=='__main__':main()
