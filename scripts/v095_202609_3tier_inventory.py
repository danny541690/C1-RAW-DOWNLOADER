"""2026-09 v0.93 -> v0.95 3-tier source reconciliation, evidence-only.
The user requires: v0.93 existing original > 6 official > FinMind Free; no empty fields fabricated.
This audit does not overwrite original source or silently publish incomplete data.
"""
import collections,csv,hashlib,io,json,os,pathlib,time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE=pathlib.Path('governance/v095')
MIG=BASE/'202609_BRONZE_MIGRATION_RESUME_20261105.json'
CON=BASE/'DATASET_CONTRACTS.csv'
DEST='1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk'
MONTH='2026-09'
OUT=pathlib.Path('v095_202609_3tier_inventory')
OUT.mkdir(exist_ok=True)
def api():
    c=Credentials(token=None,refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
      token_uri='https://oauth2.googleapis.com/token',client_id=os.environ['GOOGLE_CLIENT_ID'],
      client_secret=os.environ['GOOGLE_CLIENT_SECRET'],scopes=['https://www.googleapis.com/auth/drive'])
    c.refresh(Request())
    return build('drive','v3',credentials=c,cache_discovery=False)
def retry(factory):
    err=None
    for i in range(4):
        try:return factory().execute()
        except (OSError,ConnectionError,TimeoutError) as e:
            err=e
            time.sleep(2**i*2)
    raise err
def ls(s,folder):
    out=[];token=None
    while True:
        q=retry(lambda:s.files().list(q=f"'{folder}' in parents and trashed = false",
             pageToken=token,pageSize=1000,
             fields='nextPageToken,files(id,name,mimeType,size,md5Checksum,modifiedTime)'))
        out+=q.get('files',[])
        token=q.get('nextPageToken')
        if not token:return out
def main():
    manifest=json.loads(MIG.read_text())
    contracts=list(csv.DictReader(CON.open(encoding='utf-8',newline='')))
    s=api();records=[];observed_bytes=0
    folders={}
    for group in manifest['source_month_folders']:
        source=group['source'];folder=group['drive_folder_id']
        files=ls(s,folder);names=collections.defaultdict(list)
        for f in files:names[f['name']].append(f)
        folders[source]={'observed_files':len(files),'observed_bytes':sum(int(f.get('size',0)) for f in files)}
        observed_bytes+=folders[source]['observed_bytes']
        for ref in group['files']:
            matched=[f for f in names.get(ref['name'],[]) if f['id']==ref['id']]
            if not matched:matched=names.get(ref['name'],[])
            if not matched:status='MISSING_V095';bytes_found=None
            elif len(matched)>1:status='DUPLICATE_SAME_NAME';bytes_found=None
            else:
                f=matched[0]
                bytes_found=int(f.get('size',0))
                status='OBSERVED_SIZE_MATCH' if bytes_found==int(ref['bytes']) else 'SIZE_MISMATCH'
            records.append({'source':source,'file_name':ref['name'],'legacy_migration_ref_id':ref['id'],
                            'v095_observed_size':bytes_found,'manifest_size':ref['bytes'],
                            'status':status,'source_priority':'V093_READONLY_REUSE_FIRST',
                            'next_route':'V093_FIND_AND_VERIFY' if status!='OBSERVED_SIZE_MATCH' else 'CHECK_SOURCE_CONTRACT',
                            'sha256_readback_this_run':False,
                            'pit_verified':False})
    groups=collections.Counter(x['source_class_id'] for x in contracts)
    pending=[x for x in records if x['status']!='OBSERVED_SIZE_MATCH']
    # Dataset expected units have to be signed separately; file count is NOT market coverage.
    report={'schema':'JARVIS_V095_202609_3TIER_REAL_INVENTORY_V1','month':MONTH,
      'source_order':['V093_EXISTING_ORIGINAL','OFFICIAL_TWSE_TPEX_MOPS_TDCC_TAIFEX_NDC','FINMIND_FREE_EQUIVALENT_GAPS_ONLY'],
      'source_year_coverage':'OBSERVED_OBJECTS_ONLY',
      'v093_to_v095_manifest_count':len(records),
      'v095_matched_name_and_size':sum(x['status']=='OBSERVED_SIZE_MATCH' for x in records),
      'v095_manifest_mismatches':len(pending),
      'observed_v095_month_folder_bytes':observed_bytes,'by_source':folders,
      'contract_candidates':len(contracts),'contract_source_counts':dict(groups),
      'contract_signed':False,'dataset_universe_coverage_certified':False,
      'original_source_sha_verified_for_all':False,
      'finmind_backfill_authorized_only_after_official_unsupported':True,
      'missing_value_policy':'NULL_PLUS_REASON_AND_ASOF_NO_FORCED_ZERO',
      'pit_pass':False,'all_443_gold_computed':False,
      'full_release_approved':False,
      'next_steps':{'missing_existing':'search immutable v0.93, copy only missing and compare SHA256',
        'official':'after v0.93 exhaustion request exact official dataset/date only, 3 bounded attempts',
        'finmind':'only API-available officially equivalent fields still missing, store separately',
        'silver':'Parquet typed, source version, date, native unit, published_at, availability_at',
        'gold':'443 feature dependency DAG, warmup, partial NULL, PIT fail closed; no XQ broker fabrications'}}
    # The separate runtime doesn't certify SHA merely based on file size.
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (OUT/'manifest_diffs.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'source_inventory.csv').open('w',newline='',encoding='utf-8') as f:
        cols=list(records[0]);w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(records)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    # Drive report is supplemental QA, never mistaken for immutable Bronze.
    name='JARVIS_v095_202609_3TIER_INVENTORY_'+os.getenv('GITHUB_RUN_ID','LOCAL')+'.json'
    b=(OUT/'summary.json').read_bytes()
    from googleapiclient.http import MediaIoBaseUpload
    x=retry(lambda:s.files().create(body={'name':name,'parents':[DEST]},
          media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype='application/json',resumable=False),
          fields='id,name,size'))
    if hashlib.sha256(retry(lambda:s.files().get_media(fileId=x['id']))).digest()!=hashlib.sha256(b).digest():
        raise ValueError('REPORT_READBACK_SHA_MISMATCH')
    print('QA_REPORT_DRIVE_ID',x['id'],flush=True)
if __name__=='__main__':main()
