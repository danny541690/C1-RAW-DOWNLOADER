"""Always produce one finite, honest cross-job release report from archived artifacts."""
import json,os
from pathlib import Path

def main():
 root=Path('collected');out=Path('results');out.mkdir(exist_ok=True)
 def find(name):
  paths=sorted(root.rglob(name))
  return json.loads(paths[0].read_text()) if paths else None
 needs=json.loads(os.environ['BATCH_NEEDS']);catalog=find('candidate-catalogs.json');runtime=find('real-continuous.json');audit=find('old-writer-audit.json');offline=find('full-repo-summary.json')
 entries=[]
 for path in root.rglob('entry.json'):
  value=json.loads(path.read_text());entries.append(dict(source=value['source'],slot=value['slot'],statuses=value['task_status_counts']))
 result=dict(schema='JARVIS_OVERNIGHT_MERGED_RELEASE_REPORT_V1',run_id=os.environ['GITHUB_RUN_ID'],source_sha=os.environ['GITHUB_SHA'],jobs={k:v['result'] for k,v in needs.items()},offline=offline,entry_fixtures=entries,candidate_catalogs=catalog,real_retained_continuous=runtime,old_writer_audit=audit,production_activation=False,deployment_ready=False,source_download_requests=0,formal_raw_writes=0,data_repaired=0,confirmed_historical_exceptions=0,
  remaining_release_gates=[dict(id='G1',item='Candidate retained catalogs must incorporate later QA outcomes and approved missing/correction contracts before production release; missing/held scope is preserved in frozen review'),dict(id='G2',item='Actual native positive missing download and invalid-old-file correction/save/reverify for approved source types; existing retained rechecks and entry fixtures do not replace this'),dict(id='G3',item='Continuous loop and gated ten-minute recovery controller are implemented; actual released twelve-worker quota/heartbeat/storage throughput and provider failover remain unmeasured'),dict(id='G4',item='Merge fixed tested revision, approve release manifest only after required gates, then validate first formal batch')],historical_empty_backlog_nonblocking=1602)
 result['implemented_batch_passed']=all(v['result']=='success' for v in needs.values()) and len(entries)==12 and bool(audit and audit['passed']) and bool(runtime)
 (out/'overnight-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 lines=['# 上線前一次合併批次結果',f"Run {result['run_id']}，SHA {result['source_sha']}",'',f"已實作批次測試通過：{result['implemented_batch_passed']}。正式上線：尚未放行。",'', '| 階段 | 結果 |','|---|---|']+[f'|{k}|{v}| ' for k,v in result['jobs'].items()]
 lines+=['',f"整倉庫結果：{offline}；十二入口fixture結果共{len(entries)}份。",'來源下載0、正式RAW寫入0、資料修復0；既有檔檢查件數與日期見real_retained_continuous，不冒充全庫資料驗收。','','## 剩餘門檻']+[f"- {g['id']}: {g['item']}" for g in result['remaining_release_gates']]
 (out/'overnight-summary.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(implemented_batch_passed=result['implemented_batch_passed'],jobs=result['jobs'],offline=offline,entry_count=len(entries),production_activation=False)),flush=True)
 if not result['implemented_batch_passed']:raise RuntimeError('OVERNIGHT_BATCH_HAS_FAILURE_OR_MISSING_EVIDENCE')
if __name__=='__main__':main()
