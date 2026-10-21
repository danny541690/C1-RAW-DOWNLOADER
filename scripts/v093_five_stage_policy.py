"""User-adopted five-stage policy. Pure decisions; no downloads or activation.

Legacy CLI workers fail closed until integrated. Config adoption does not turn a
prelaunch workflow into a production worker or approve any market data.
"""
import argparse,calendar,datetime,hashlib,json,pathlib,re
from zoneinfo import ZoneInfo

VERSION='V093_FIVE_STAGE_DOWNLOAD_RULES_V1_20261021'
PATH=pathlib.Path(__file__).resolve().parents[1]/'config/v093_five_stage_policy.json'

def load_policy():
    policy=json.loads(PATH.read_text())
    if policy.get('policy_version')!=VERSION:raise ValueError('POLICY_VERSION_MISMATCH')
    if policy['retry']['max_total_attempts']!=1+policy['retry']['max_additional_retries']:raise ValueError('RETRY_DEFINITION_CONFLICT')
    if policy['reuse']['skip_whole_month_if_any_file_exists'] or policy['activation']['enable_schedules_now']:raise ValueError('UNAPPROVED_POLICY_ACTIVATION_OR_MONTH_SKIP')
    return policy

def policy_digest():return hashlib.sha256(PATH.read_bytes()).hexdigest()

def as_of():return datetime.datetime.now(ZoneInfo(load_policy()['timezone'])).date()

def historical_months(today=None):
    today=today or as_of()
    return [f'{y:04d}-{m:02d}' for y in range(today.year,1999,-1) for m in range(12,0,-1) if (y,m)<=(today.year,today.month)]

def bounded_month(month,today=None):
    today=today or as_of()
    if not re.fullmatch(r'20\d{2}-\d{2}',month):raise ValueError('INVALID_MONTH')
    y,m=map(int,month.split('-'))
    start=datetime.date(y,m,1)
    if month<'2000-01' or start>today:raise ValueError('MONTH_OUTSIDE_AVAILABLE_SCOPE')
    return start.isoformat(),min(datetime.date(y,m,calendar.monthrange(y,m)[1]),today).isoformat()

def unit_key(unit):
    fields=load_policy()['unit_identity']
    if any(not isinstance(unit.get(k),str) or not unit[k] for k in fields):raise ValueError('INCOMPLETE_UNIT_IDENTITY')
    start=datetime.date.fromisoformat(unit['period_start']);end=datetime.date.fromisoformat(unit['period_end'])
    if start>end:raise ValueError('REVERSED_UNIT_PERIOD')
    return hashlib.sha256(json.dumps([unit[k] for k in fields],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def reuse_action(receipt,actual_sha256=None,*,file_exists=False):
    if not receipt:return 'VERIFY_EXISTING_FIRST' if file_exists else 'DOWNLOAD_MISSING_UNIT'
    if receipt.get('database_version')!='0.93':return 'BLOCK_LEGACY_OR_UNPROVEN_DATABASE'
    digest=receipt.get('sha256')
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):return 'VERIFY_EXISTING_FIRST'
    if actual_sha256!=digest:return 'QUARANTINE_HASH_CONFLICT' if actual_sha256 else 'VERIFY_EXISTING_FIRST'
    checks=('durable_readback','source_identity_ok','date_identity_ok','security_identity_ok','basic_format_ok')
    return 'REUSE_SAVED_BASIC_UNIT' if all(receipt.get(k) is True for k in checks) else 'VERIFY_EXISTING_FIRST'

def retry_action(attempts,error_class):
    p=load_policy()['retry']
    if type(attempts) is not int or attempts<0:raise ValueError('INVALID_ATTEMPT_COUNT')
    if error_class=='UNKNOWN_AFTER_CRASH':return 'RECONCILE_BEFORE_REPLAY'
    if error_class not in p['transient']:return 'ISOLATE_AND_REPORT'
    return 'BACKOFF_AND_RETRY' if attempts<p['max_total_attempts'] else 'QUEUE_REPAIR_AND_CONTINUE'

def finmind_eligible(gap):
    return (gap.get('official_source') in load_policy()['sources']['official'] and
            gap.get('missing_unit_confirmed') is True and gap.get('official_evidence_sha256') is not None and
            bool(re.fullmatch('[a-f0-9]{64}',str(gap.get('official_evidence_sha256')))) and
            all(gap.get(k) is True for k in ('definition_compatible','unit_compatible','sign_compatible','frequency_compatible','availability_compatible')))

def prelaunch(stage):
    p=load_policy()
    if stage not in p['stages']:raise ValueError('UNKNOWN_STAGE')
    return {'stage':stage,'policy_version':VERSION,'policy_sha256':policy_digest(),
            'effective_months':len(historical_months()),'dependencies':p['dependencies'][stage],
            'max_total_attempts':p['retry']['max_total_attempts'],'runtime':'PRELAUNCH_ONLY_NOT_IMPLEMENTED'}

def block_legacy_cli(worker):
    load_policy()
    raise SystemExit('LEGACY_WORKER_POLICY_NOT_INTEGRATED:'+worker+'; required='+VERSION+'; no download started')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['RAW','QA1','PRICE','FINANCIAL','CHIP'],required=True)
    print(json.dumps(prelaunch(parser.parse_args().stage),ensure_ascii=False,sort_keys=True))
