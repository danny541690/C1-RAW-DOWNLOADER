import sys,json,zipfile,hashlib,csv,gzip,io,collections,datetime
from pathlib import Path
sys.path.insert(0,str(Path('round3_work').resolve()))
from scripts.v093_standard_r4 import parse_member,decode
from scripts.v093_cross_source_numeric_audit import compare_rows,is_mapped_native_field
p=Path('round3_evidence');cache=Path('prelaunch_real');sha=lambda b:hashlib.sha256(b).hexdigest();metric_names=('open','high','low','close');data={s:[] for s in ('FinMind','TWSE','TPEx')};files=[];targets=set();observed_finmind_keys=set();excluded_ohlc={s:set() for s in ('FinMind','TWSE','TPEx')};days={s:set() for s in ('TWSE','TPEx')}
expected={a['id']:a['sha256'] for s in json.load(open('prelaunch_cross_round/native_inventory.json'))['sources'] for a in s.get('archives',[]) if a.get('sha256')}
with gzip.open('round3_work/reports/raw-register/20261027_v1/units/TPEx_units.csv.gz','rt',encoding='utf-8-sig') as f:ledger={r['原件參照']:r for r in csv.DictReader(f)}
def accept(source,cells):
 for r in cells:
  if not r['date_content_verified']:continue
  if source=='FinMind':observed_finmind_keys.add((r['date'],r['stock_id']))
  if r.get('ohlc_violation'):
   excluded_ohlc[source].add((r['date'],r['stock_id']));continue
  if source!='FinMind' and (r['date'],r['stock_id']) not in targets:continue
  if any(is_mapped_native_field(source,m,r['native_field']) for m in metric_names):
   r['numeric_unscaled']=float(r['numeric_decimal_text']);data[source].append(r)
   if source=='FinMind':targets.add((r['date'],r['stock_id']))
for fid in ('1Vf_woRGApwCYIr8_tMkkX-U5W6wvKNCm','1VIZmRgbZSzWQKey-jDfNuy5rcXxn6dkb','1dBD17dBFCfOr69UTTeTSAg_FBsEGXR3i'):
 b=(cache/fid).read_bytes()
 if fid in expected:assert sha(b)==expected[fid]
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert z.testzip() is None
  manifests=json.loads(z.read('complement_manifest_R1.json')) if 'complement_manifest_R1.json' in z.namelist() else None
  hashes={Path(r['file']).name:r['sha256'] for r in manifests['files']} if manifests else {}
  for name in z.namelist():
   if not ((name.startswith('price_complement_') and name.endswith('.jsonl')) or (name.startswith('TaiwanStockPrice/') and name.endswith('.json'))):continue
   raw=z.read(name)
   if manifests:assert sha(raw)==hashes[name]
   cells,stats,enc=parse_member('FinMind',name,raw,'2026-09');accept('FinMind',cells);files.append(dict(source='FinMind',archive_id=fid,archive_sha256=sha(b),member=name,sha256=sha(raw),integrity='PRIOR_MANIFEST_MATCH' if manifests else 'NEW_SNAPSHOT_SHA_PARENT_RESPONSE_NOT_READBACK'))
stockcodes={k[1] for k in targets}
for source,fid in [('TWSE','1GU6S_QqJsIdljQviXIpZE2e2Nm-Zquq6'),('TPEx','1uqHfQLV--3wLROFhTtt8dl-Gb5aDDEef'),('TPEx','1MHMveRwByWuc5v5pjS1n_i3Dr8-SZ7fl'),('TPEx','1-LacMHLRFczb9I-LA3MddWRLwskMyy72'),('TPEx','1yGCCksAm8XnGQF37mbdBvj0if9IegHKC')]:
 b=(cache/fid).read_bytes()
 if fid in expected:assert sha(b)==expected[fid]
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert z.testzip() is None
  for name in z.namelist():
   ref=fid+'/'+name;receipt=ledger.get(ref)
   chosen=(name.startswith('prices_indices_') and name.endswith('.raw')) if source=='TWSE' else ((name.startswith(('prices_','complement_prices_','csv_alternate_prices_')) and name.endswith(('.raw','.csv'))) or (receipt and receipt['資料集']=='prices' and receipt['月份']=='2026-09'))
   if not chosen:continue
   raw=z.read(name)
   if receipt and receipt['已下載']=='1':assert sha(raw)==receipt['RAW_SHA256']
   if name.endswith('.csv'):
    text,enc=decode(raw);grid=list(csv.reader(io.StringIO(text)));hi=next(i for i,row in enumerate(grid) if '代號' in row);ci=grid[hi].index('代號');kept=grid[:hi+1]+[row for row in grid[hi+1:] if len(row)>ci and row[ci].strip() in stockcodes]
    buf=io.StringIO();csv.writer(buf).writerows(kept);selected=buf.getvalue().encode()
   else:
    obj=json.loads(raw)
    for t in obj.get('tables') or [obj]:
     fields=t.get('fields',[]);ci=next((i for i,k in enumerate(fields) if k in ('證券代號','代號','股票代號')),None);t['data']=[r for r in t.get('data',[]) if isinstance(r,list) and ci is not None and len(r)>ci and str(r[ci]).strip() in stockcodes]
    selected=json.dumps(obj,ensure_ascii=False).encode()
   cells,stats,enc=parse_member(source,name,selected,'2026-09');accept(source,cells);days[source].update(r['date'] for r in cells if r['date_content_verified']);files.append(dict(source=source,archive_id=fid,member=name,raw_sha256=sha(raw),selected_payload_sha256=sha(selected),selection='EXACT_FINMIND_CODES_ONLY',date_proofs=sorted({r['date_proof'] for r in cells})))
checks={m:compare_rows(data,m,abs_tol=0.01) for m in metric_names};keys={s:{(r['date'],r['stock_id']) for r in rows} for s,rows in data.items()};unmatched=sorted(targets-keys['TWSE']-keys['TPEx'])
r={'checked_at_taipei':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'period':'2026-09','inputs':files,'finmind_artifacts':sum(f['source']=='FinMind' for f in files),'finmind_observed_date_code_keys':len(observed_finmind_keys),'finmind_eligible_date_code_keys':len(targets),'excluded_ohlc_keys':{s:sorted(v) for s,v in excluded_ohlc.items()},'overlap_date_code_keys':{s:len(keys[s]&targets) for s in ('TWSE','TPEx')},'matched_finmind_keys_by_source':{s:sorted(keys[s]&targets) for s in ('TWSE','TPEx')},'checks':checks,'unmatched_finmind_date_code_keys':unmatched,'official_price_days':{s:sorted(d) for s,d in days.items()},'independent_numeric_verified':False,'unit_contract_verified':False,'pit_verified':False,'universe_verified':False,'approved_scopes':[],'formal_release':'BLOCKED','notes':['Artifact representations are deduplicated by exact date/code for numeric pairs; conflicting same-source values excluded','Comparison is diagnostic, not independent upstream verification','New free-tier archive SHA captured this round, parent API response SHA not verified by fetching full annual response','CSV dates are proved by native header, not filename alone']}
(p/'round3_actual_cross_results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print({k:r[k] for k in ('finmind_artifacts','finmind_observed_date_code_keys','finmind_eligible_date_code_keys','overlap_date_code_keys')});print('unmatched',len(unmatched))
for m,v in checks.items():print(m,v['compared_pairs'],v['mismatch'],'conflicts',v['duplicate_conflicts'])
