"""Full-menu TDCC ownership, independent of legacy 2026-05 partition.

A frozen manifest must be persisted and fenced before runners use it. This does
not infer history outside the menu or replace the old live TDCC entry point.
"""
import datetime as dt,hashlib,json

def build_scope(dates,as_of,prior=None):
    upper=dt.date.fromisoformat(as_of);floor=dt.date(2000,1,1);valid=set();held=[]
    for value in dates:
        try:
            date=dt.datetime.strptime(value,'%Y%m%d').date()
            if len(value)!=8:raise ValueError('DATE_FORMAT')
        except (TypeError,ValueError):raise ValueError('TDCC_MENU_DATE_INVALID') from None
        if date<floor or date>upper:held.append(value)
        else:valid.add(value)
    if prior:
        verify_scope(prior)
        if prior['as_of']!=as_of:raise ValueError('CAMPAIGN_AS_OF_CHANGED')
        # Existing scope is immutable; newly offered dates must be a separate
        # generation, never silently move current owners or reset their cursor.
        all_old=set(prior['owners']['ASC'])|set(prior['owners']['DESC'])
        return dict(scope=prior,new_dates_pending=sorted(valid-all_old,reverse=True),
                    old_dates_no_longer_in_menu=sorted(all_old-valid),outside_campaign=sorted(held))
    ordered=sorted(valid);mid=len(ordered)//2
    body=dict(schema='JARVIS_TDCC_FROZEN_SCOPE_V1',as_of=as_of,
        owners=dict(ASC=ordered[:mid],DESC=list(reversed(ordered[mid:]))),
        actual_menu_scope_only=True,historical_universe_complete=False,
        shared_distributed_lease_verified=False,legacy_receipts_migrated=False)
    body['scope_id']=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    return dict(scope=body,new_dates_pending=[],old_dates_no_longer_in_menu=[],outside_campaign=sorted(held))

def verify_scope(scope):
    body=dict(scope);claimed=body.pop('scope_id',None)
    if scope.get('schema')!='JARVIS_TDCC_FROZEN_SCOPE_V1':raise ValueError('SCOPE_SCHEMA')
    if hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()!=claimed:raise ValueError('SCOPE_HASH_MISMATCH')
    upper=dt.date.fromisoformat(scope['as_of'])
    a=scope['owners']['ASC'];d=scope['owners']['DESC']
    if not isinstance(a,list) or not isinstance(d,list):raise ValueError('SCOPE_OWNER_SCHEMA')
    for value in a+d:
        date=dt.datetime.strptime(value,'%Y%m%d').date()
        if len(value)!=8 or not dt.date(2000,1,1)<=date<=upper:raise ValueError('SCOPE_DATE_OUT_OF_BOUNDS')
    if a!=sorted(set(a)) or d!=sorted(set(d),reverse=True) or set(a)&set(d):raise ValueError('SCOPE_OVERLAP_OR_ORDER')
    return scope
