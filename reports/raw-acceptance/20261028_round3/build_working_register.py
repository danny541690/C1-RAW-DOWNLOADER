import csv,gzip,json,hashlib,zipfile,shutil
from pathlib import Path
base=Path('round3_work/reports/raw-register/20261027_v1/units');out=Path('round3_register');out.mkdir(exist_ok=True);cache=Path('prelaunch_real');report=Path('round3_evidence');artifacts=[];base_refs=set()
for p in base.glob('*_units.csv.gz'):
 shutil.copy(p,out/p.name)
 with gzip.open(p,'rt',encoding='utf-8-sig') as f:
  reader=csv.DictReader(f);columns=reader.fieldnames
  for row in reader:base_refs.add(row['原件參照'])
sha=lambda b:hashlib.sha256(b).hexdigest()
for folder in ('round3_evidence','prelaunch_cross_round'):
 for fid in ['1MHMveRwByWuc5v5pjS1n_i3Dr8-SZ7fl','1-LacMHLRFczb9I-LA3MddWRLwskMyy72','1yGCCksAm8XnGQF37mbdBvj0if9IegHKC','1VIZmRgbZSzWQKey-jDfNuy5rcXxn6dkb','1dBD17dBFCfOr69UTTeTSAg_FBsEGXR3i','1Vf_woRGApwCYIr8_tMkkX-U5W6wvKNCm']:
  p=Path(folder)/fid
  if p.is_file() and not (cache/fid).exists():shutil.copy(p,cache/fid)
for fid in ['1Vf_woRGApwCYIr8_tMkkX-U5W6wvKNCm','1VIZmRgbZSzWQKey-jDfNuy5rcXxn6dkb','1dBD17dBFCfOr69UTTeTSAg_FBsEGXR3i']:
 with zipfile.ZipFile(cache/fid) as z:
  assert z.testzip() is None
  manifest=json.loads(z.read('complement_manifest_R1.json')) if 'complement_manifest_R1.json' in z.namelist() else None
  hashes={Path(x['file']).name:x['sha256'] for x in manifest['files']} if manifest else {}
  for n in z.namelist():
   if not ((n.startswith('price_complement_') and n.endswith('.jsonl')) or (n.startswith('TaiwanStockPrice/') and n.endswith('.json'))):continue
   b=z.read(n);raw_sha=sha(b)
   if manifest:assert raw_sha==hashes[n]
   if n.endswith('.jsonl'):records=[json.loads(l)['source_record'] for l in b.decode().splitlines() if l.strip()];code=records[0]['stock_id']
   else:obj=json.loads(b);records=obj['rows'];code=obj['stock_id']
   assert records and all(r['stock_id']==code and r['date'].startswith('2026-09') for r in records)
   artifacts.append(dict(source='FinMind',dataset='TaiwanStockPrice',month='2026-09',period='2026-09',code=code,ref=fid+'/'+n,sha256=raw_sha,records=len(records),archive_sha256=sha((cache/fid).read_bytes()),integrity='PRIOR_MEMBER_MANIFEST_SHA_MATCH' if manifest else 'NEW_SNAPSHOT_SHA_CAPTURED_PARENT_REPLY_NOT_READBACK_VERIFIED'))
with zipfile.ZipFile(cache/'1uqHfQLV--3wLROFhTtt8dl-Gb5aDDEef') as z:
 for n in z.namelist():
  if n.startswith('csv_alternate_prices_202609'):
   d=n.split('_')[3];period=d[:4]+'-'+d[4:6]+'-'+d[6:];artifacts.append(dict(source='TPEx',dataset='prices',month='2026-09',period=period,code='',ref='1uqHfQLV--3wLROFhTtt8dl-Gb5aDDEef/'+n,sha256=sha(z.read(n)),archive_sha256=sha((cache/'1uqHfQLV--3wLROFhTtt8dl-Gb5aDDEef').read_bytes()),integrity='EXISTING_ARCHIVE_SHA_BOUND_NATIVE_CSV'))
added=[]
with gzip.open(out/'supplemental_artifacts_units.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
 for a in artifacts:
  if a['ref'] in base_refs:continue
  row={c:'' for c in columns};row.update({'來源':a['source'],'資料集':a['dataset'],'月份':a['month'],'年份':'2026','期間':a['period'],'代碼':a['code'],'單元ID':'supp_'+sha(a['ref'].encode())[:24],'原件參照':a['ref'],'RAW_SHA256':a['sha256'],'已下載':'1','基本格式存檔通過':'0','已保存待內容驗證':'1','未下載':'0','明列品質問題':'0','預期代碼':'[]','RAW狀態':'SUPPLEMENTAL_ARTIFACT_CAPTURED_NOT_UNIVERSE','計畫母體性質':'原件版本盤點；不得當應有母體分母','快照ID':'RETAINED_SUPPLEMENTAL_ARTIFACTS_20261028'})
  writer.writerow(row);added.append(a)
(report/'supplemental_artifacts_register.json').write_text(json.dumps(dict(base_snapshot='20261027_V1_UNCHANGED',added_artifacts=len(added),unique_logical_source_dataset_month_code=len({(a['source'],a['dataset'],a['month'],a['code']) for a in added}),universe_approved=False,artifacts=added),ensure_ascii=False,indent=2)+'\n')
print('supplemental artifacts',len(added))
