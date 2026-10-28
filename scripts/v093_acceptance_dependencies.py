"""Content-addressed checker dependencies; unrelated scripts do not invalidate RAW checks."""
import ast,hashlib,json
from pathlib import Path

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def dependency_manifest(root,modules):
 root=Path(root);todo=list(modules);seen={}
 while todo:
  module=todo.pop();p=root/('scripts/'+module+'.py')
  if module in seen:continue
  if not p.is_file():raise ValueError('CHECKER_DEPENDENCY_MISSING:'+module)
  data=p.read_bytes();seen[module]=hashlib.sha256(data).hexdigest();tree=ast.parse(data)
  for n in ast.walk(tree):
   if isinstance(n,ast.ImportFrom) and n.module:
    if n.module.startswith('scripts.'):todo.append(n.module.split('.')[1])
    elif n.module=='scripts':todo.extend(a.name for a in n.names)
   elif isinstance(n,ast.Import):
    todo.extend(a.name.split('.')[1] for a in n.names if a.name.startswith('scripts.'))
 # Requirements changes may alter parser behaviour, even without source changes.
 lock=root/'requirements-qa.lock'
 if lock.exists():seen['requirements-qa.lock']=hashlib.sha256(lock.read_bytes()).hexdigest()
 return seen

SOURCE_MODULES={
 'FinMind':['v093_esb_market_evidence'],
 'MOPS':['v093_stage06_financial_repair','v093_official_content_audit'],
 'TWSE':['v093_official_content_audit'],
 'TPEx':['v093_official_content_audit','v093_standard_r4'],
 'TAIFEX':['v093_taifex_independent'],
 'TDCC':['v093_tdcc_independent'],
 'NDC':[],
}
def checker_signatures(root):
 root=Path(root);shared={}
 for name in ('v093_prelaunch_acceptance_batch','v093_acceptance_dependencies'):
  p=root/'scripts'/(name+'.py');shared[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 return {s:digest(dict(shared=shared,dependencies=dependency_manifest(root,mods))) for s,mods in SOURCE_MODULES.items()}

def cache_token(row,raw_sha,archive_sha,checker_signature,esb_evidence):
 code=row.get('代碼');month=row.get('月份')
 scoped=[(k,v) for k,v in sorted(esb_evidence.items()) if row['來源']=='FinMind' and k[1]==code and k[0].startswith(month or '!')]
 return digest(dict(task=row,raw_sha256=raw_sha,archive_sha256=archive_sha,checker_signature=checker_signature,dated_esb_evidence=scoped))
