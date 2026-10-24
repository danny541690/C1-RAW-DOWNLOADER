"""Offline reparse and durable due-month scheduling; never downloads source RAW."""
import hashlib
import time
import re
from lxml import html
from scripts import v093_stage06_financial_repair as financial

REPARSE_REVISION='MOPS_REPARSE_READBACK_V1'
def digest(raw):return hashlib.sha256(raw).hexdigest()

def reparse_financial(raw,job,expected_sha,owned,write,read):
    """Publish an isolated derivative receipt only after complete native roundtrip."""
    if digest(raw)!=expected_sha:raise ValueError('REPARSE_INPUT_SHA_MISMATCH')
    if job.get('codes'):
        root=html.fromstring(raw.decode('utf-8-sig'))
        supplied={match.group(1) for value in root.xpath('//input[@name="reportName"]/@value')
                  if (match:=re.match(r'([0-9A-Za-z]{4,8})\s',value.strip()))}
        missing=set(job['codes'])-supplied
        if missing:raise ValueError('FINANCIAL_SOURCE_COMPANIES_MISSING:'+','.join(sorted(missing)))
    unit=dict(source=job['source'],market='UNKNOWN',dataset=job['category'],security_id='ALL_MARKET',
              period_start=job['period'],period_end=job['period'],native_unit_id=job['unit_id'])
    output=financial.transform(raw,unit)
    financial.validate_output(raw,output,unit)
    name=job['unit_id']+'_'+expected_sha+'_'+REPARSE_REVISION+'.parquet'
    owned();write(name,output);owned()
    remote=read(name)
    if remote is None or digest(remote)!=digest(output):raise ValueError('REPARSE_OUTPUT_READBACK_SHA_MISMATCH')
    evidence=financial.validate_output(raw,remote,unit)['evidence']
    owned()
    return dict(status='REPARSED_READBACK_VERIFIED_OPEN_QUALITY_ITEMS',output_name=name,
                raw_sha256=expected_sha,output_sha256=digest(remote),parser_revision=REPARSE_REVISION,
                remote_readback_hash_verified=True,evidence=evidence,
                complete=False,numeric_verified=False,pit_verified=False)

def pending_month(journal):
    """No-data, blocked routes and quality work are distinct from due transport retries."""
    rows=list(journal.get('units',{}).values())
    pending=[r for r in rows if not r.get('terminal') and not r.get('complete')]
    return dict(next_retry_at=min((r.get('next_retry_at',0) for r in pending),default=None),
                retry_units=len(pending),
                blocked_units=sum(r.get('terminal',False) and not r.get('complete',False) for r in rows),
                source_empty_units=sum(r.get('status')=='SOURCE_NO_DATA_UNCONFIRMED' for r in rows))

def due_months(index,now=None):
    instant=time.time() if now is None else now
    return sorted((m for m,s in index.items() if s.get('next_retry_at') is not None
                   and s['next_retry_at']<=instant),key=lambda m:(index[m]['next_retry_at'],m))
