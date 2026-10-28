"""Executable design preview. No network access, source writes or production activation."""
import argparse,datetime as dt,json
from pathlib import Path
SOURCES=('TWSE','TPEx','MOPS','TAIFEX','TDCC','NDC','FinMind')

def months_desc(as_of, floor='2000-01'):
    upper=dt.date.fromisoformat(as_of)
    y,m=map(int,floor.split('-'));lower=dt.date(y,m,1)
    if lower>upper:raise ValueError('INVALID_DATE_SCOPE')
    out=[];current=upper.replace(day=1)
    while current>=lower:
        out.append(current.strftime('%Y-%m'))
        current=(current-dt.timedelta(days=1)).replace(day=1)
    return out

def validate_config(config):
    if config['schema']!='JARVIS_SEVEN_SOURCE_DESIGN_V1':raise ValueError('SCHEMA')
    lanes=config['lanes']
    if len(lanes)!=7 or {x['source'] for x in lanes}!=set(SOURCES):raise ValueError('EXACT_SEVEN_SOURCES')
    if config['direction']!='DESC' or config['floor']!='2000-01':raise ValueError('DIRECTION_SCOPE')
    if config['attempts']['max_total']!=4 or config['attempts']['reset_on_restart']:raise ValueError('RETRY_POLICY')
    if config['activate_production'] is not False:raise ValueError('PREVIEW_NOT_ACTIVATION')
    for field in ('workflow','lock','state_branch'):
        if len({x[field] for x in lanes})!=7:raise ValueError('SHARED_'+field.upper())
    return config

def eligible_gap(gap, as_of):
    # A legacy missing flag, timeout, 404, or empty result alone is not authority.
    return (gap.get('official_source') in SOURCES[:3]
        and gap.get('official_evidence_id') and gap.get('confirmed_gap') is True
        and gap.get('period','9999')[:10]<=as_of
        and gap.get('identity_period_market_verified') is True
        and gap.get('definition_unit_frequency_verified') is True
        and gap.get('stock_id') and gap.get('dataset'))

def build_plan(config,source,as_of,gaps=()):
    validate_config(config)
    upper=dt.date.fromisoformat(as_of)
    if upper>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date():raise ValueError('FUTURE_AS_OF')
    lane=next((x for x in config['lanes'] if x['source']==source),None)
    if lane is None:raise ValueError('SOURCE')
    months=months_desc(as_of,config['floor'])
    eligible=[g for g in gaps if eligible_gap(g,as_of)] if source=='FinMind' else []
    return dict(schema='JARVIS_SEVEN_SOURCE_PREVIEW_V1',source=source,as_of=as_of,
        execution_mode='DESIGN_PREVIEW_ONLY',market_requests=0,production_writes=0,
        activate_production=False,month_priority=months if source!='FinMind' else [],
        month_count=len(months),month_count_is_expected_data_unit_denominator=False,
        latest_partial_month=months[0],eligible_finmind_gap_tasks=len(eligible),
        finmind_task_order=sorted([{'dataset':g['dataset'],'stock_id':g['stock_id'],'period':g['period']} for g in eligible],key=lambda x:x['period'],reverse=True),
        lane=lane,states=config['states'],readiness_blockers=lane['readiness_blockers'],
        estimated_completion=None,formal_release='BLOCKED')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True)
    p.add_argument('--as-of',default=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat())
    p.add_argument('--config',type=Path,default=Path('config/v093_seven_source_design.json'))
    p.add_argument('--gaps',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    c=json.loads(a.config.read_text());g=json.loads(a.gaps.read_text()) if a.gaps else []
    result=build_plan(c,a.source,a.as_of,g)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('month_priority','states')},ensure_ascii=False))
if __name__=='__main__':main()
