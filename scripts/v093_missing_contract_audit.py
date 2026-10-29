"""Diagnose download eligibility against frozen receipts without any market/Drive I/O."""
import collections,gzip,json
from pathlib import Path
from scripts import v093_three_year_repair as native
from scripts.v093_official_firstpass import LOWER_BOUNDS
def main():
 manifest=json.loads(Path('original/ledger_manifest.json').read_text())
 review=json.loads(gzip.decompress(Path('frozen/TWSE.review.json.gz').read_bytes()))
 counts=collections.Counter();examples={};categories=collections.Counter();trading=set();primary=[]
 for f in manifest:
  if '/RAW/' not in f['path'] or '/RECONCILE_REPAIR/' in f['path'] or f['name']!='MONTH_STATE.json':continue
  doc=json.loads(gzip.decompress((Path('original')/f['local']).read_bytes()));primary.append((f,doc))
  for r in doc.get('units',{}).values():
   if r.get('source')=='TWSE' and r.get('category') in ('prices','prices_indices') and r.get('status')=='SAVED_BASIC_VERIFIED':trading.add(r.get('period'))
 for f,doc in primary:
  for key,r in doc.get('units',{}).items():
   if r.get('source')!='TWSE':continue
   categories[r.get('category')]+=1
   task='TWSE|'+f['path'].split('/RAW/')[1][:7]+'|'+r.get('unit_id',key);item=review['tasks'].get(task)
   period=r.get('period','');cat=r.get('category')
   reason=('HAS_RETAINED_REFERENCE' if r.get('evidence_file') else
    'TASK_NOT_IN_REVIEW' if not item else
    'REVIEW_ACTION_'+item['action'] if item['action']!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE' else
    'CATEGORY_NOT_NATIVE_DAILY' if cat not in {x[0] for x in native.DAILY['TWSE']} else
    'TRADING_DAY_NOT_PROVEN' if period not in trading else
    'SOURCE_START_UNPROVEN' if ('TWSE',cat) not in LOWER_BOUNDS else
    'BEFORE_SOURCE_START' if period<LOWER_BOUNDS['TWSE',cat] else 'ELIGIBLE')
   counts[reason]+=1
   if len(examples.setdefault(reason,[]))<5:examples[reason].append(dict(key=key,task=task,period=period,category=cat,status=r.get('status'),fields=list(r),path=f['path']))
 out=dict(schema='JARVIS_MISSING_CONTRACT_AUDIT_V1',counts=dict(counts),examples=examples,categories=dict(categories),proven_trading_dates=len(trading),market_requests=0,drive_requests=0)
 Path('results').mkdir(exist_ok=True);Path('results/selector-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
