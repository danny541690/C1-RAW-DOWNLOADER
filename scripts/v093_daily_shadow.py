"""Bounded official daily RAW capture and unapproved QA report.

No FinMind quota, no user strategy, no approved pointer writes. Reuses durable receipts.
"""
import datetime as dt,hashlib,io,json,os,urllib.request,zipfile
from zoneinfo import ZoneInfo
from scripts.bulk_monthly_capture import url_for
from scripts.v093_standard_r4 import day,parse_member,SCHEMA,VERSION
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.v093_standard_r1 import ROOT,C1

def target_day(now=None):
    now=now or dt.datetime.now(ZoneInfo('Asia/Taipei'))
    d=now.date() if now.hour>=18 else now.date()-dt.timedelta(days=1)
    while d.weekday()>=5:d-=dt.timedelta(days=1)
    return d

def capture(d,registry,qa,run_day=None):
    trade_day=run_day or target_day();period=trade_day.strftime('%Y-%m')
    shadow=registry.folder(qa,'DAILY_SHADOW',True)
    name=trade_day.isoformat()+'_OFFICIAL_SHADOW_V1.json'
    prior=d.read(shadow,name)
    report=json.loads(prior) if prior else {'trade_date':trade_day.isoformat(),'sources':{},'status':'IN_PROGRESS','production_ready':False}
    for source in ('TWSE','TPEx'):
        old=report['sources'].get(source,{})
        if old.get('status')=='RAW_AND_CANDIDATE_READBACK_PASS':
            payload=d.read(old['raw_folder'],old['raw_name'])
            candidate=d.read(old['candidate_folder'],old['candidate_name'])
            if payload and candidate and hashlib.sha256(payload).hexdigest()==old['sha256'] and hashlib.sha256(candidate).hexdigest()==old['candidate_sha256']:
                old['resumed']=True;continue
            old['status']='PRIOR_READBACK_MISMATCH'
            continue
        attempts=old.get('attempts',0)
        if attempts>=4:continue
        rec={'attempts':attempts+1,'status':'REQUEST_RESERVED'};report['sources'][source]=rec
        d.put(shadow,name,json.dumps(report,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
        try:
            req=urllib.request.Request(url_for(source,trade_day),headers={'User-Agent':'Mozilla/5.0 JARVIS-v093-shadow'})
            with urllib.request.urlopen(req,timeout=35) as resp:raw=resp.read(15_000_001)
            if len(raw)>15_000_000:raise ValueError('SOURCE_RESPONSE_LIMIT')
            obj=json.loads(raw);rd=day(obj.get('date')) if isinstance(obj,dict) else None
            if rd!=trade_day.isoformat():raise ValueError('RESPONSE_CONTENT_DATE_NOT_PROVEN')
            if source=='TWSE' and obj.get('stat')!='OK':raise ValueError('SOURCE_NOT_OK_OR_NONTRADING_DAY_UNCONFIRMED')
            mh=hashlib.sha256(raw).hexdigest();member=source+'_'+trade_day.strftime('%Y%m%d')+'.json'
            rows,counts,enc=parse_member(source,member,raw,period)
            if not rows:raise ValueError('NO_NUMERIC_SECURITY_ROWS')
            rawfolder=registry.folder(registry.folder(registry.folder(ROOT,str(trade_day.year),True),source,True),period,True)
            fetched=dt.datetime.now(dt.timezone.utc).isoformat();archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr(member,raw)
                z.writestr('manifest.json',json.dumps({'source':source,'url':url_for(source,trade_day),'trade_date':rd,'retrieved_at':fetched,'member_sha256':mh,'source_contract_approved':False,'pit_verified':False}))
            native=archive.getvalue();rawname='DAILY_SHADOW_V1_'+source+'_'+trade_day.isoformat()+'_'+mh[:18]+'.zip'
            # An interrupted save is recovered by immutable source-digest naming.
            existing=d.read(rawfolder,rawname)
            if existing:
                with zipfile.ZipFile(io.BytesIO(existing)) as z:
                    if z.testzip() or hashlib.sha256(z.read(member)).hexdigest()!=mh:raise ValueError('EXISTING_RAW_MISMATCH')
                native=existing
            else:d.put(rawfolder,rawname,native)
            readback=d.read(rawfolder,rawname)
            if hashlib.sha256(readback).digest()!=hashlib.sha256(native).digest():raise ValueError('RAW_READBACK')
            for row in rows:row.update(native_archive=rawname,native_sha256=hashlib.sha256(native).hexdigest(),native_member_sha256=mh)
            candidate_folder=registry.folder(shadow,'CANDIDATES',True)
            out=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),out,compression='zstd');body=out.getvalue()
            cname=source+'_'+trade_day.isoformat()+'_'+mh[:18]+'_'+VERSION+'.parquet'
            d.put(candidate_folder,cname,body)
            back=d.read(candidate_folder,cname)
            if hashlib.sha256(back).digest()!=hashlib.sha256(body).digest() or pq.read_metadata(io.BytesIO(back)).num_rows!=len(rows):raise ValueError('CANDIDATE_READBACK')
            rec.update(status='RAW_AND_CANDIDATE_READBACK_PASS',raw_folder=rawfolder,raw_name=rawname,sha256=hashlib.sha256(native).hexdigest(),candidate_folder=candidate_folder,candidate_name=cname,candidate_sha256=hashlib.sha256(body).hexdigest(),staged_cells=len(rows),checks=counts,retrieved_at=fetched,encoding=enc,production_ready=False)
        except Exception as exc:rec.update(status='SOURCE_HOLD',reason=type(exc).__name__+':'+str(exc)[:200])
        report['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        d.put(shadow,name,json.dumps(report,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    report['status']='SHADOW_NOT_APPROVED'
    report['blockers']=['SOURCE_FIELD_UNIT_CONTRACT_NOT_APPROVED','EXPECTED_HISTORICAL_UNIVERSE_UNKNOWN','FEATURE_GOLDEN_AND_WARMUP_NOT_APPROVED','PIT_AND_RELEASE_EVIDENCE_INCOMPLETE']
    report['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    d.put(shadow,name,json.dumps(report,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    report_dir=registry.folder(C1,'07_REPORTS')
    text='# Daily shadow '+trade_day.isoformat()+'\n\n狀態：未核准，不是正式選股訊號。\n\n'+ '\n'.join('- '+s+': '+r['status']+'；數值欄位 '+str(r.get('staged_cells',0)) for s,r in report['sources'].items())+'\n\n待驗證：來源欄位與單位、歷史證券母體、指標暖機與Golden、公告時點及發布證據。\n'
    d.put(report_dir,trade_day.isoformat()+'_DAILY_SHADOW_V1.md',text.encode(),'text/markdown',overwrite=True)
    return report

