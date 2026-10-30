import json,os
from pathlib import Path

def main():
 root=Path('collected');out=Path('results');out.mkdir(exist_ok=True)
 def read(name):
  paths=sorted(root.rglob(name));return json.loads(paths[0].read_text()) if paths else None
 needs=json.loads(os.environ['BATCH_NEEDS']);capture=read('native-missing-capture.json');resume=read('native-missing-resume.json');audit=read('old-writer-audit.json');offline=read('full-repo-summary.json')
 r=dict(schema='JARVIS_NATIVE_POSITIVE_MERGED_BATCH_V1',run_id=os.environ['GITHUB_RUN_ID'],source_sha=os.environ['GITHUB_SHA'],jobs={k:v['result'] for k,v in needs.items()},offline=offline,capture=capture,cold_resume=resume,old_writer_audit=audit,production_activation=False,formal_raw_writes=0,formal_data_repaired=0,limitation='Positive missing native adapter acceptance and repair control regression; no claim that all source formats, real corrupted market RAW repairs, production catalogs or long-run quotas are accepted')
 r['implemented_batch_passed']=all(v=='success' for v in r['jobs'].values()) and bool(resume and resume['qa_downloaded_and_basic_verified'])
 (out/'native-merged-summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(jobs=r['jobs'],implemented_batch_passed=r['implemented_batch_passed'],offline=offline,qa_downloaded_and_verified=(resume or {}).get('qa_downloaded_and_basic_verified',0),formal_data_repaired=0,production_activation=False)),flush=True)
 if not r['implemented_batch_passed']:raise ValueError('NATIVE_MERGED_BATCH_INCOMPLETE')
if __name__=='__main__':main()
