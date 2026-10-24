"""Real Drive reparse roundtrip in per-run sandbox. No official RAW mutations."""
import argparse,hashlib,io,json,os,pathlib,time,zipfile
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_prelaunch_live_recovery import context,sandbox
from scripts import v093_five_stage_durable_gate as gate
from scripts.v093_repair_execution import reparse_financial

SOURCE_ZIP='1oOiOX6zDRAUoWWbfJtQNuyLJTO3rHSAk'
MISSING_UNIT='654fa677c284792a1eb211ea'
EXPECTED_MISSING='FINANCIAL_SOURCE_COMPANIES_MISSING:9103,9105,9110,9136'

def main(phase):
    run,url,token=context();d=Drive(service());d.direct_readback=True
    parent=d.folder(sandbox(d,run,create=False),'FINANCIAL_REPARSE')
    prior_raw=d.read(parent,'ACCEPTANCE.json')
    prior=json.loads(prior_raw) if prior_raw else None
    if phase=='restart' and not prior:raise ValueError('RESTART_PROOF_MISSING')
    if phase=='write' and prior:raise ValueError('UNEXPECTED_EXISTING_PROOF')
    key='financial-reparse';owner=run+'-'+phase
    fence=gate.acquire(url,token,key,owner,ttl=600)
    def owned():
        _,manifest=gate._read(url,token);lease=manifest['jobs'][key].get('lease') or {}
        if lease.get('owner')!=owner or lease.get('fence')!=fence or lease.get('expires_at',0)<=time.time():
            raise gate.LeaseConflict('STALE_OR_EXPIRED_WRITER')
    raw=d.call(lambda:d.api.files().get_media(fileId=SOURCE_ZIP))
    if len(raw)>10_000_000:raise ValueError('SOURCE_ARCHIVE_LIMIT')
    records=[];successes=0;cells=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(x.file_size for x in z.infolist())>64_000_000:raise ValueError('ZIP_EXPANSION_LIMIT')
        jobs=json.loads(z.read('manifest.json'))['units']
        if len(jobs)!=6:raise ValueError('SOURCE_UNIT_COUNT_CHANGED')
        for job in jobs:
            if not job.get('sha256'):raise ValueError('SOURCE_MANIFEST_SHA_MISSING')
            payload=z.read(job['file'])
            try:
                receipt=reparse_financial(payload,job,job['sha256'],owned,
                    lambda n,b:d.put(parent,n,b,'application/octet-stream',overwrite=False),
                    lambda n:d.read(parent,n))
            except ValueError as exc:
                if job['unit_id']!=MISSING_UNIT or str(exc)!=EXPECTED_MISSING:raise
                records.append(dict(unit_id=job['unit_id'],status='EXPECTED_SOURCE_CONTENT_INCOMPLETE',error=str(exc)))
                continue
            if job['unit_id']==MISSING_UNIT:raise ValueError('INCOMPLETE_SOURCE_WAS_ACCEPTED')
            fid=d.find(parent,receipt['output_name'])['id']
            records.append(dict(unit_id=job['unit_id'],file_id=fid,**receipt))
            successes+=1;cells+=receipt['evidence']['cells_compared']
    if successes!=5 or cells!=4975:raise ValueError('DERIVED_CELL_OR_UNIT_COUNT_CHANGED')
    if prior:
        before={r['unit_id']:(r.get('file_id'),r.get('output_sha256')) for r in prior['results']}
        after={r['unit_id']:(r.get('file_id'),r.get('output_sha256')) for r in records}
        if before!=after:raise ValueError('RESTART_CREATED_DUPLICATE_OR_CHANGED_OUTPUT')
    proof=dict(run_id=run,phase=phase,successfully_reparsed_units=successes,cells_roundtripped=cells,
        source_incomplete_units=1,results=records,test_parent_id=parent,
        source_archive_id=SOURCE_ZIP,source_archive_sha256=hashlib.sha256(raw).hexdigest(),
        real_google_drive_write_readback=True,cross_job_resume=bool(prior),
        source_download_requests=0,production_raw_writes=0,production_schedules_changed=False,
        numeric_semantics_verified=False,pit_verified=False,production_gate='BLOCKED')
    output=json.dumps(proof,ensure_ascii=False,sort_keys=True).encode()
    owned();d.put(parent,'ACCEPTANCE.json',output,'application/json',overwrite=True);owned()
    if d.read(parent,'ACCEPTANCE.json')!=output:raise ValueError('PROOF_READBACK_MISMATCH')
    gate.commit(url,token,key,owner,fence,hashlib.sha256(output).hexdigest())
    pathlib.Path('reports').mkdir(exist_ok=True)
    pathlib.Path('reports/four-lane-live-'+phase+'.json').write_bytes(output)
    print('FOUR_LANE_LIVE_ACCEPTANCE_PASS '+json.dumps({k:v for k,v in proof.items() if k!='results'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['write','restart']);main(p.parse_args().phase)
