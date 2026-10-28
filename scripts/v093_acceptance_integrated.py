"""Single read-only entry point for content checks, scoped evidence and all 37 gaps.

This does not implement missing universe/PIT/production validators. Missing
capabilities block release explicitly rather than masquerading as test passes.
"""
import argparse,collections,csv,datetime,gzip,hashlib,json,shutil,time,zipfile
from pathlib import Path
from scripts import v093_prelaunch_acceptance_batch as batch
from scripts.v093_acceptance_dependencies import digest

def read_artifact(path):
 b=Path(path).read_bytes();return json.loads(b),dict(file=Path(path).name,sha256=batch.sha(b))

def metric_count(value):
 if isinstance(value,int) and not isinstance(value,bool) and value>=0:return value
 if isinstance(value,dict) and all(isinstance(n,int) and not isinstance(n,bool) and n>=0 for n in value.values()):return sum(value.values())
 raise ValueError('DIAGNOSTIC_METRIC_SCHEMA')

def verify_diagnostic(path,cache,archives):
 obj,ref=read_artifact(path);checked=0;errors=[]
 if not isinstance(obj.get('inputs'),list) or not obj['inputs']:raise ValueError('DIAGNOSTIC_INPUT_MANIFEST_MISSING')
 for entry in obj['inputs']:
  try:
   raw,archive_sha=batch.retained_raw(cache,entry['archive_id']+'/'+entry['member'],archives)
   if raw is None:raise ValueError('DIAGNOSTIC_RAW_NOT_IN_CACHE')
   if batch.sha(raw)!=entry.get('sha256',entry.get('raw_sha256')):raise ValueError('DIAGNOSTIC_RAW_SHA_MISMATCH')
   if entry.get('archive_sha256') and archive_sha!=entry['archive_sha256']:raise ValueError('DIAGNOSTIC_ARCHIVE_SHA_MISMATCH')
   checked+=1
  except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:errors.append(dict(input=entry,error=str(e)))
 return dict(artifact=ref,input_references_checked=checked,input_errors=errors,result='INPUTS_REVALIDATED_HISTORICAL_DIAGNOSTIC' if not errors else 'INVALIDATED_DIAGNOSTIC',recomputed_numeric_pairs=False,reported_field_pairs=sum(metric_count(x.get('compared_pairs',0)) for x in obj.get('checks',{}).values()),reported_mismatches=sum(metric_count(x.get('mismatch',0)) for x in obj.get('checks',{}).values()),independence_verified=False,full_scope_verified=False)

def recover_readback_scope(summary,content,cache,out,archives):
 if not summary.get('archive_readbacks'):return dict(result='NOT_EXECUTED_NO_READBACK_SCOPE',files_restored=[],units_verified=0,errors=[],scope='NO_RESTORABLE_INPUTS',full_database_restore_verified=False,remote_backup_rechecked=False,account_loss_recovery_verified=False)
 restored=out/'restored_raw'
 if restored.exists() and any(restored.iterdir()):raise ValueError('RESTORE_TARGET_NOT_EMPTY')
 restored.mkdir(exist_ok=True);files=[];errors=[]
 for fid,expected in summary['archive_readbacks'].items():
  try:
   raw,sha=archives[fid]
   if sha!=expected['sha256']:raise ValueError('RECOVERY_INPUT_CHANGED')
   dest=restored/fid;dest.write_bytes(raw)
   if batch.sha(dest.read_bytes())!=sha:raise ValueError('RESTORE_SHA_MISMATCH')
   files.append(dict(file_id=fid,sha256=sha,bytes=len(raw),result='PASS_LOCAL_RESTORE_SHA'))
  except (OSError,ValueError) as e:errors.append(dict(file_id=fid,error=str(e)))
 units=0;restored_cache=batch.ArchiveCache()
 for ev in content:
  try:
   raw,_=batch.retained_raw(restored,ev['raw_reference'],restored_cache)
   if raw is None or batch.sha(raw)!=ev['raw_sha256']:raise ValueError('RESTORED_MEMBER_SHA_MISMATCH')
   units+=1
  except (OSError,ValueError,KeyError) as e:errors.append(dict(task_key=ev['task_key'],error=str(e)))
 return dict(result='PASS_LOCAL_READBACK_SCOPE_RECOVERY' if not errors else 'FAIL_LOCAL_RECOVERY',files_restored=files,units_verified=units,errors=errors,scope='ONLY_RAW_PACKAGES_READ_IN_THIS_CONTENT_BATCH',full_database_restore_verified=False,remote_backup_rechecked=False,account_loss_recovery_verified=False)

RULE_REASONS={
 'R01':'核准母體與最新全量遠端收據對帳尚缺',
 'R02':'全範圍歷史證券有效期間及日曆證據未齊',
 'R03':'全資料集欄位單位契約與適用性未齊',
 'R04':'未讀回原件、未覆蓋資料集與內容錯誤仍待處理',
 'R05':'跨來源結果僅診斷，完整範圍及上游獨立性未驗',
 'R06':'歷史當時可得時間與原版／更正版證據及全量檢查器未齊',
 'R07':'前置實際證據不足；正式發布、下游及回復未執行',
 'R08':'已讀回原件的本機復原不等於全庫遠端復原與鮮度驗收',
}

def aggregate(plan,summary,content,diagnostic=None,recovery=None,remote=None):
 # Ownership lists must match the original 37-rule catalog. No user-supplied
 # passed flags or group labels are accepted as a release proof.
 canonical=Path(__file__).resolve().parent.parent/'reports/raw-acceptance/20261027_v1/acceptance_rules.json'
 expected={r['規格ID'] for r in json.loads(canonical.read_text())['rules']}
 ownership=plan['rule_ownership'];ids=[r['rule_id'] for r in ownership]
 if len(ids)!=37 or len(set(ids))!=37 or set(ids)!=expected:raise ValueError('EXACT_37_RULE_OWNERSHIP_REQUIRED')
 group_ids=[g['id'] for g in plan['groups']]
 if len(group_ids)!=8 or set(group_ids)!={f'R{i:02d}' for i in range(1,9)} or any(r['primary_group'] not in group_ids for r in ownership):raise ValueError('EXACT_EIGHT_GROUPS_REQUIRED')
 counts=summary['counts'];esb=sum(len(e['content'].get('esb_raw_only_rows',[])) for e in content)
 observed={g:[] for g in group_ids}
 if counts.get('units'):observed['R01'].append(dict(kind='REGISTER_SCAN_NOT_APPROVED_UNIVERSE',records=counts['units']))
 dated=sum(e['source']=='FinMind' and e['dataset']=='TaiwanStockPrice' for e in content)
 if dated:observed['R02'].append(dict(kind='FINITE_PRICE_DATES_CODES_KEYS_CHECKED_WITHIN_RETAINED_INPUTS',artifact_records=dated))
 if esb:observed['R03'].append(dict(kind='DATED_ESB_FIELDS_COMPARED_RAW_ONLY',rows=esb))
 if content:observed['R04'].append(dict(kind='PARTIAL_RAW_CONTENT',artifact_records=len(content),blocked_artifacts=counts.get('CONTENT_BLOCKED',0)))
 if diagnostic and diagnostic.get('result')=='INPUTS_REVALIDATED_HISTORICAL_DIAGNOSTIC':observed['R05'].append(dict(kind='HISTORICAL_DIAGNOSTIC_INPUTS_STILL_MATCH',references=diagnostic['input_references_checked'],reported_field_pairs=diagnostic['reported_field_pairs']))
 if recovery and recovery.get('result')=='PASS_LOCAL_READBACK_SCOPE_RECOVERY':observed['R08'].append(dict(kind='LOCAL_READBACK_SCOPE_RECOVERY',packages=len(recovery['files_restored']),units=recovery['units_verified']))
 if remote:observed['R01'].append(dict(kind='SCOPED_REMOTE_METADATA_ONLY',folders=len(remote.get('folders',[])),global_enumeration_complete=False))
 rules=[dict(rule_id=r['rule_id'],name=r['name'],group=r['primary_group'],full_scope_result='UNKNOWN',reason=RULE_REASONS[r['primary_group']],observations=observed[r['primary_group']],execution_coverage='PARTIAL_ADAPTERS' if observed[r['primary_group']] else 'NO_FULL_SCOPE_EXECUTOR_OR_EVIDENCE',requires_action=True) for r in ownership]
 groups=[dict(id=g['id'],name=g['name'],result='BLOCKED' if g['id']=='R07' else 'PARTIAL' if observed[g['id']] else 'UNKNOWN',complete=False,observations=observed[g['id']],remaining=RULE_REASONS[g['id']],rules=[r['rule_id'] for r in rules if r['group']==g['id']]) for g in plan['groups']]
 return dict(groups=groups,group_counts=dict(collections.Counter(g['result'] for g in groups)),completed_groups=0,rules=rules,rule_counts=dict(collections.Counter(r['full_scope_result'] for r in rules)),approved_universe=None,approved_scopes=[],formal_release='BLOCKED',production_published=False)

def triage_content_failures(content_dir,cache,archives):
 from lxml import html
 result=[]
 with gzip.open(content_dir/'next_round.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   if r['status']!='CONTENT_BLOCKED':continue
   item=dict(task_key=r['task_key'],source=r['source'],dataset=r['dataset'],period=r['period'],raw_reference=r['raw_reference'],raw_sha256=r['raw_sha256'],original_error=r['next_action'],diagnosis='UNRESOLVED_CONTENT_FAILURE',proposed_queue='REPAIR_CONTENT',raw_changed=False)
   try:
    raw,_=batch.retained_raw(cache,r['raw_reference'],archives)
    if raw is None or batch.sha(raw)!=r['raw_sha256']:raise ValueError('TRIAGE_RAW_SHA_MISMATCH')
    if r['source']=='MOPS' and r['dataset'] in ('BalanceSheet','IncomeStatement','CashflowStatement'):
     doc=html.fromstring(raw.decode('utf-8-sig'));bodies=doc.xpath('//*[@id="bodyTable"]//tbody');rows=doc.xpath('//*[@id="bodyTable"]//tbody/tr');period=doc.xpath('//input[@name="yearseason"]/@value')
     expected=r['period'][:4]+'Q'+str((int(r['period'][5:7])-1)//3+1)
     item.update(body_tables=len(bodies),account_rows=len(rows),response_period=period,company_headers=len(doc.xpath('//input[@name="reportName"]')))
     if bodies and not rows and period==[expected]:item.update(diagnosis='RETAINED_MOPS_RESPONSE_HAS_NO_ACCOUNT_ROWS',proposed_queue='SOURCE_ROUTE_REVIEW',next_action='保留原件；查證前2013歷史財報路由或其他可追溯原始報表，不能靠解析修復空數值表，也不能據此斷言歷史資料不存在')
   except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:item['triage_error']=str(e)
   result.append(item)
 return result

def queue_counts_and_copy(content_dir,out,triage=None):
 counts=collections.Counter();cols=None;overrides={r['task_key']:r['proposed_queue'] for r in triage or []}
 queues=out/'repair_queue.csv.gz'
 with gzip.open(content_dir/'next_round.csv.gz','rt',encoding='utf-8-sig',newline='') as inp,gzip.open(queues,'wt',encoding='utf-8-sig',newline='') as dest:
  reader=csv.DictReader(inp);cols=reader.fieldnames+['queue'];writer=csv.DictWriter(dest,fieldnames=cols);writer.writeheader()
  mapping={'RAW_NOT_IN_LOCAL_CACHE':'READBACK_EXISTING','RECONCILE_FROZEN_MISSING':'RECONCILE_LATEST','CONTENT_BLOCKED':'REPAIR_CONTENT','ESB_RAW_ONLY_RULES_OPEN':'REVIEW_ESB_RAW_ONLY','REMAINING_RULES_OPEN':'COMPLETE_EVIDENCE'}
  for row in reader:
   queue=overrides.get(row['task_key'],mapping.get(row['status'],'REVIEW_UNKNOWN'));counts[queue]+=1;writer.writerow(dict(row,queue=queue))
 return dict(counts)

def run(register,cache,out,plan_file,resume=None,esb_dir=None,diagnostic_file=None,remote_file=None):
 start=time.monotonic();out=Path(out);out.mkdir(parents=True,exist_ok=True);archives=batch.ArchiveCache();stages=[]
 plan,plan_ref=read_artifact(plan_file)
 content_dir=out/'content';summary=batch.run(Path(register),Path(cache),content_dir,Path(resume) if resume else None,Path(esb_dir) if esb_dir else None,archives)
 content=json.loads((content_dir/'raw_content_evidence.json').read_text());stages.append(dict(stage='content',result='COMPLETED_WITH_OPEN_ITEMS',counts=summary['counts']))
 diagnostic=None
 if diagnostic_file:
  try:diagnostic=verify_diagnostic(diagnostic_file,Path(cache),archives)
  except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:diagnostic=dict(result='DIAGNOSTIC_ERROR',error=str(e))
 stages.append(dict(stage='cross_source',result=diagnostic['result'] if diagnostic else 'NOT_PROVIDED_BLOCKED'))
 try:recovery=recover_readback_scope(summary,content,Path(cache),out,archives)
 except (ValueError,KeyError,OSError) as e:recovery=dict(result='RECOVERY_ERROR',error=str(e))
 stages.append(dict(stage='recovery',result=recovery['result']))
 remote=None;remote_ref=None
 if remote_file:
  try:remote,remote_ref=read_artifact(remote_file)
  except (ValueError,OSError) as e:stages.append(dict(stage='remote_inventory',result='REMOTE_ARTIFACT_ERROR',error=str(e)))
 result=aggregate(plan,summary,content,diagnostic,recovery,remote)
 triage=triage_content_failures(content_dir,Path(cache),archives)
 queues=queue_counts_and_copy(content_dir,out,triage)
 result.update(version='JARVIS_INTEGRATED_READONLY_V1',run_id='integrated_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'),checked_at_taipei=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),stages=stages,input_plan=plan_ref,remote_snapshot=remote_ref,diagnostic=diagnostic,recovery=recovery,content_triage=triage,queues=queues,content_counts=summary['counts'],elapsed_seconds=round(time.monotonic()-start,3),cache_metrics=dict(packages=len(archives),unique_member_extractions=archives.member_extractions),source_downloads=0,production_writes=0,limitations=['Full remote inventory, approved universe, full PIT and production validators are not implemented by this entry point','37 UNKNOWN full-scope rule results are explicit gaps, not passes','Historical diagnostic numbers are reused only after input SHA readback; numeric comparisons not rerun'])
 for name,obj in [('integrated_summary.json',result),('rule_results.json',result['rules']),('group_results.json',result['groups']),('content_triage.json',triage)]:(out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 report=['# 賈維斯合併執行結果','',f"八組完成 {result['completed_groups']}/8；狀態 {result['group_counts']}。正式發布 BLOCKED。",'',f"內容清單 {summary['counts']}。",'', '| 組別 | 狀態 | 尚缺條件 |','|---|---|---|']+[f"| {g['id']} {g['name']} | {g['result']} | {g['remaining']} |" for g in result['groups']]
 report+=['','所有 37 條全範圍規格仍為 UNKNOWN；已完成的是本次可執行的內容、證據讀回與局部復原，不代表全庫八組通過。','',f"本輪時間 {result['elapsed_seconds']} 秒；佇列 {queues}。查詢單元／補存版本混合筆數不可當作完整性分母。"]
 (out/'README.md').write_text('\n'.join(report)+'\n');return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--register',required=True,type=Path);p.add_argument('--raw-cache',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--plan',required=True,type=Path);p.add_argument('--resume',type=Path);p.add_argument('--esb-evidence',type=Path);p.add_argument('--diagnostic',type=Path);p.add_argument('--remote-snapshot',type=Path);a=p.parse_args();r=run(a.register,a.raw_cache,a.out,a.plan,a.resume,a.esb_evidence,a.diagnostic,a.remote_snapshot);print(json.dumps({k:r[k] for k in ('run_id','group_counts','completed_groups','content_counts','queues','elapsed_seconds','formal_release')},ensure_ascii=False))
if __name__=='__main__':main()
