"""Reconcile RAW-root metadata with retained register; never infers global Drive absence."""
import argparse,collections,csv,gzip,hashlib,json,pathlib

def run(register,snapshot,out):
 register=pathlib.Path(register);out=pathlib.Path(out);out.mkdir(exist_ok=True,parents=True);raw=pathlib.Path(snapshot).read_bytes();snap=json.loads(raw)
 if snap.get('schema')!='JARVIS_REMOTE_METADATA_V1' or snap.get('enumeration_complete') is not True or snap.get('error') or snap.get('phase')!='DONE':raise ValueError('REMOTE_ENUMERATION_NOT_COMPLETE')
 if snap.get('root')!='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn':raise ValueError('REMOTE_ROOT_SCOPE_MISMATCH')
 files={f['id']:f for f in snap['files']};allids=set(files);physical={k for k,v in files.items() if v['mimeType']!='application/vnd.google-apps.folder'}
 count=collections.Counter();sources=collections.defaultdict(collections.Counter);periods=collections.defaultdict(collections.Counter);register_hashes={};package_refs=set();metadata_hits=set();not_observed=set()
 cols=['source','dataset','year','month','period','task_key','raw_reference','registered_raw_sha256','register_download_flag','metadata_result','metadata_name','metadata_size','metadata_modified_time','next_action']
 with gzip.open(out/'remote_register_reconciliation.csv.gz','wt',encoding='utf-8-sig',newline='') as dest:
  w=csv.DictWriter(dest,fieldnames=cols);w.writeheader()
  for p in sorted(register.glob('*_units.csv.gz')):
   register_hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
   with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
     ref=r.get('原件參照','');fid=ref.split('/',1)[0];meta=files.get(fid);downloaded=r['已下載']=='1'
     if not downloaded:status='FROZEN_MISSING_NEEDS_CURRENT_RECEIPTS';action='先對帳最新收據與核准母體，不能僅靠檔案 metadata 修補此旗標'
     elif fid in physical:status='PACKAGE_METADATA_PRESENT_NOT_CONTENT_VERIFIED';action='可讀回既有原件並驗 SHA／成員；metadata 存在不代表單元通過'
     elif fid in allids:status='REFERENCE_POINTS_TO_FOLDER';action='核對原件參照與收據，資料夾不能當 RAW 檔案'
     else:status='NOT_OBSERVED_IN_ENUMERATED_RAW_SCOPE';action='先查原件ID是否位於其他資料夾、已移轉或有新版本；不直接宣稱 Drive 未下載'
     count[status]+=1;sources[r['來源']][status]+=1;periods[(r['來源'],r['年份'],r['月份'])][status]+=1
     if downloaded:
      package_refs.add(fid)
      if fid in physical:metadata_hits.add(fid)
      else:not_observed.add(fid)
     w.writerow(dict(source=r['來源'],dataset=r['資料集'],year=r['年份'],month=r['月份'],period=r['期間'],task_key=r['來源']+'|'+r['單元ID'],raw_reference=ref,registered_raw_sha256=r['RAW_SHA256'],register_download_flag=r['已下載'],metadata_result=status,metadata_name=meta.get('name','') if meta else '',metadata_size=meta.get('size','') if meta else '',metadata_modified_time=meta.get('modifiedTime','') if meta else '',next_action=action))
 summary=dict(kind='METADATA_TO_RETAINED_REGISTER_RECONCILIATION',metadata_started_at=snap['started_at'],metadata_updated_at=snap['updated_at'],metadata_snapshot_sha256=hashlib.sha256(raw).hexdigest(),register_sha256=register_hashes,enumeration_complete_for_filtered_raw_scope=True,atomic_point_in_time_snapshot=False,metadata_file_records=len(physical),metadata_folder_records=len(allids)-len(physical),registered_record_counts=dict(count),sources={s:dict(v) for s,v in sources.items()},unique_referenced_packages=len(package_refs),referenced_packages_metadata_present=len(metadata_hits),referenced_packages_not_observed=len(not_observed),unreferenced_metadata_files=len(physical-metadata_hits),unreferenced_metadata_files_are_missing_data=False,global_drive_absence_verified=False,raw_sha_readback_verified=False,approved_universe=None,formal_release='BLOCKED',note='Register includes historical task units and supplemental artifact versions; metadata file counts and task counts are different units. Snapshot listing covers exact year/source roots, not all Drive.')
 (out/'remote_reconciliation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 (out/'source_year_month_metadata_counts.json').write_text(json.dumps([dict(source=k[0],year=k[1],month=k[2],counts=dict(v)) for k,v in sorted(periods.items())],ensure_ascii=False,indent=2))
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--register',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(run(a.register,a.snapshot,a.out),ensure_ascii=False))
