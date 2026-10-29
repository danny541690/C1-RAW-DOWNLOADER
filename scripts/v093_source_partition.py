"""Deterministic workload partition contract, not a distributed execution lease."""
import datetime as dt,hashlib,json,math
COUNTS={'TWSE':2,'TPEx':2,'MOPS':2,'TAIFEX':2,'TDCC':2,'NDC':1,'FinMind':1}

def partition(rows,source,as_of):
    if source not in COUNTS:raise ValueError('UNKNOWN_SOURCE')
    upper=dt.date.fromisoformat(as_of);ready=[];held=[];seen=set()
    for row in rows:
        if row['source']!=source:continue
        key=row['key']
        if key in seen:raise ValueError('DUPLICATE_LOGICAL_TASK')
        seen.add(key)
        value=row['period'];date=dt.date.fromisoformat(value+'-01' if len(value)==7 else value)
        reason=('OUTSIDE_CAMPAIGN' if not dt.date(2000,1,1)<=date<=upper else
                'APPLICABILITY_NOT_PROVEN' if row.get('availability')!='PROVEN_APPLICABLE' else None)
        if reason:held.append(dict(key=key,reason=reason));continue
        cost=row.get('estimated_cost',1)
        if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<=0:
            raise ValueError('INVALID_WORK_COST')
        ready.append(dict(row,estimated_cost=cost))
    ready.sort(key=lambda r:(r['period'],r['key']),reverse=True)
    if COUNTS[source]==1:head=ready;tail=[]
    else:
        target=sum(r['estimated_cost'] for r in ready)/2;running=0;best=0;distance=target
        for i,row in enumerate(ready,1):
            running+=row['estimated_cost']
            if abs(running-target)<distance:best=i;distance=abs(running-target)
        # Keep one task per side whenever possible, even with a very large item.
        if len(ready)>1:best=max(1,min(len(ready)-1,best))
        elif ready:best=1
        head=ready[:best];tail=list(reversed(ready[best:]))
    result=dict(source=source,as_of=as_of,latest_first=[r['key'] for r in head],
        oldest_first=[r['key'] for r in tail],held=held,
        latest_cost=sum(r['estimated_cost'] for r in head),oldest_cost=sum(r['estimated_cost'] for r in tail),
        input_tasks=len(seen),distributed_claims_verified=False)
    assert len(set(result['latest_first']+result['oldest_first']))+len(held)==len(seen)
    result['manifest_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
