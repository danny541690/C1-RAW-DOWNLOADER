"""Read-only historical Drive ZIP verification and explicit repair planning.

Samples at most one ZIP per source/month. A zero ZIP count is a ZIP gap,
not proof of missing native non-ZIP files. Never certify coverage from this audit.
"""
import hashlib,io,json,zipfile
from scripts.v093_standard_r1 import ls,SOURCES,ROOT
from scripts.v093_five_stage_durable_gate import decide_adapter

MAX_READ=12_000_000

def inspect_zip_bytes(raw):
    digest=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        bad=z.testzip()
        if bad:raise ValueError('ZIP_CRC_ERROR:'+bad)
        members=z.namelist()
        manifest=[n for n in members if n.lower().endswith('manifest.json')]
        receipt=None
        if manifest:
            try:receipt=json.loads(z.read(manifest[0]))
            except Exception as exc:raise ValueError('ZIP_MANIFEST_INVALID') from exc
        return {'sha256':digest,'members':len(members),'has_manifest':bool(manifest),'receipt_units':len(receipt.get('units',[])) if isinstance(receipt,dict) and isinstance(receipt.get('units'),list) else None,'numeric_verified':False,'pit_verified':False,'certified':False}

def inspect_month(d,month,max_read=MAX_READ):
    year=month[:4]
    years=[x for x in ls(d,ROOT) if x['name']==year and x['mimeType']=='application/vnd.google-apps.folder']
    report={'month':month,'sources':{},'repair_queue':[],'certified':False}
    if len(years)!=1:
        report['status']='YEAR_FOLDER_MISSING_OR_AMBIGUOUS'
        return report
    children=ls(d,years[0]['id'])
    for source in SOURCES:
        sr={'zip_count':0,'sample':None}
        report['sources'][source]=sr
        folders=[x for x in children if x['name']==source and x['mimeType']=='application/vnd.google-apps.folder']
        if len(folders)!=1:
            sr['status']='SOURCE_FOLDER_MISSING_OR_AMBIGUOUS'
            report['repair_queue'].append({'month':month,'source':source,'reason':sr['status'],'action':'INVESTIGATE'})
            continue
        month_folders=[x for x in ls(d,folders[0]['id']) if x['name']==month and x['mimeType']=='application/vnd.google-apps.folder']
        if len(month_folders)!=1:
            sr['status']='MONTH_FOLDER_MISSING_OR_AMBIGUOUS'
            report['repair_queue'].append({'month':month,'source':source,'reason':sr['status'],'action':'INVESTIGATE'})
            continue
        files=ls(d,month_folders[0]['id'])
        archives=sorted((x for x in files if x['name'].lower().endswith('.zip')),key=lambda x:x['name'])
        sr['zip_count']=len(archives)
        sr['non_zip_count']=len([x for x in files if x['mimeType']!='application/vnd.google-apps.folder' and not x['name'].lower().endswith('.zip')])
        if not archives:
            sr['status']='ZIP_ABSENT_UNVERIFIED_OTHER_FORMATS'
            report['repair_queue'].append({'month':month,'source':source,'reason':sr['status'],'action':'INSPECT_OTHER_FORMATS_THEN_BACKFILL'})
            continue
        candidate=next((x for x in archives if int(x.get('size',0))<=max_read and int(x.get('size',0))>0),None)
        if candidate is None:
            sr['status']='ZIP_PRESENT_SAMPLE_UNREADABLE_SIZE_LIMIT'
            continue
        try:
            raw=d.call(lambda:d.api.files().get_media(fileId=candidate['id']))
            if len(raw)>max_read:raise ValueError('ZIP_EXCEEDS_READ_LIMIT')
            sr['sample']={'name':candidate['name'],**inspect_zip_bytes(raw)}
            sr['status']='ZIP_SAMPLE_HASH_CRC_PASS_PENDING_DEEP_QA'
        except Exception as exc:
            sr['status']='ZIP_SAMPLE_READ_OR_CRC_ERROR'
            sr['error']=type(exc).__name__+':'+str(exc)[:120]
            report['repair_queue'].append({'month':month,'source':source,'reason':sr['status'],'action':'RETRY_THEN_QUARANTINE'})
    report['status']='INVENTORIED_PENDING_QA'
    return report

def blocked_stages(report):
    result={}
    for stage in ('PRICE','FINANCIAL','CHIP'):
        result[stage]=decide_adapter(stage,None,None,None)
    return result
