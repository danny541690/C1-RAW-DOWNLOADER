"""One-run evidence inventory; separates operational rollout from data approval.

This report never enables a workflow or publishes a dataset. Missing historical
data is download backlog, not a circular prerequisite for launching a downloader.
"""
import argparse,collections,json,pathlib
import yaml
from scripts.v093_isolated_full_file_metadata_gate import summarize

STAGES=('raw','qa','price','financial','chip')

def aggregate(base='parts',root='.'):
    base=pathlib.Path(base);root=pathlib.Path(root)
    shards=[json.loads(p.read_text()) for p in base.rglob('shard.json')]
    if len(shards)!=4:raise ValueError('EXPECTED_FOUR_CURRENT_RUN_INVENTORY_SHARDS')
    inventory=summarize(shards)
    native=[json.loads(p.read_text()) for p in base.rglob('native-parser.json')]
    if {r['month'] for r in native}!={'2014-04','2024-06','2025-01','2026-09'} or len(native)!=4:
        raise ValueError('EXPECTED_FOUR_CURRENT_RUN_NATIVE_MONTHS')
    regressions=list(base.rglob('regression.json'))
    recoveries=list(base.rglob('live-recovery.json'))
    if len(regressions)!=1 or len(recoveries)!=1:raise ValueError('MISSING_CURRENT_RUN_EXECUTION_EVIDENCE')
    regression=json.loads(regressions[0].read_text());recovery=json.loads(recoveries[0].read_text())
    if not regression.get('passed'):raise ValueError('REGRESSION_NOT_PASSED')
    if not recovery_pass(recovery):raise ValueError('REAL_SANDBOX_RECOVERY_NOT_PASSED')
    stages={}
    for i,stage in enumerate(STAGES,1):
        path=root/f'.github/workflows/v093-v2-{i:02d}-{stage}.yml'
        workflow=yaml.safe_load(path.read_text());on=workflow.get('on',workflow.get(True,{}))
        steps=[step for job in workflow.get('jobs',{}).values() for step in job.get('steps',[])]
        body='\n'.join(str(s.get('run','')) for s in steps)
        state='STUB_ONLY' if 'FIVE_STAGE_PRELAUNCH_CHECK_PASS' in body else 'REAL_PATH_NOT_YET_EVIDENCE_VERIFIED'
        stages[stage.upper()]={'implementation':state,'cron_enabled':'schedule' in on,
                              'workflow':str(path.relative_to(root))}
    if any(s['cron_enabled'] for s in stages.values()):raise ValueError('UNEXPECTED_PRODUCTION_CRON_ENABLED')
    counts=collections.Counter();pairs=collections.Counter();mismatch=0
    for r in native:
        if r.get('drive_writes')!=0 or r.get('certified') is not False:raise ValueError('NATIVE_AUDIT_UNSAFE')
        for src,s in r['sources'].items():
            for k,v in s['stats'].items():counts[k]+=v
        pairs.update(r['cross_source_close']['compared_pairs'])
        mismatch+=sum(r['cross_source_close']['mismatch'].values())
    backlog={'source_month_pairs':inventory['counts']['source_month_pairs'],
             'inventory_counts':inventory['counts'],'review_queue_items':len(inventory['review_queue']),
             'effect':'Backfill and review queue; not by itself a RAW operational-launch prerequisite.'}
    gaps=[
      {'id':'OP-01','status':'NOT_IMPLEMENTED_OR_NOT_CONNECTED','requirement':'Five real RAW/QA1/PRICE/FINANCIAL/CHIP workers with actual input/output receipts; current files are prelaunch stubs.'},
      {'id':'OP-02','status':'SANDBOX_PASS_PRODUCTION_INTEGRATION_PENDING','requirement':'Connect durable lease, immutable put/readback and crash reconciliation to every real worker; this run only tests the isolated adapter.'},
      {'id':'OP-03','status':'PENDING_REAL_WORKERS','requirement':'Cancel/restart each real stage and prove no lost work, no duplicate publication and correct parent receipt binding.'},
      {'id':'OP-04','status':'PENDING_REAL_WORKERS','requirement':'Exercise cutover, old-writer drain, rollback and publication-pointer recovery against actual candidate workers.'},
      {'id':'OP-05','status':'PENDING_SUSTAINED_TEST','requirement':'Source 429/503 throttling, retry budgets, Drive/GitHub quota backpressure, throughput and memory over a sustained worker batch.'},
      {'id':'DATA-01','status':'BLOCKED','requirement':'Resolve source/archive identity, MOPS financial/revenue adapters and unparsed corporate-action members; preserve missing and unavailable history.'},
      {'id':'DATA-02','status':'BLOCKED','requirement':'Versioned units, announcement/revision dates, PIT, historical universe/calendar and independent numeric source verification for each published field.'},
    ]
    report={'operational_launch':'BLOCKED_REAL_STAGE_WORKERS_PENDING','data_publication':'BLOCKED_UNVERIFIED_DATA',
            'regression':regression,'stages':stages,'sandbox_recovery':recovery,
            'historical_backlog':backlog,'native_samples':{'months':len(native),'counts':dict(counts),
            'cross_source_close_pairs':dict(pairs),'cross_source_close_mismatches':mismatch,
            'resource_measurements':{r['month']:r.get('resources',{}) for r in native},
            'scope':'Bounded samples; not all files, securities or fields.'},
            'remaining_acceptance':gaps,'production_data_writes':0,'schedules_enabled':False,'certified':False}
    return report,inventory

def main():
    p=argparse.ArgumentParser();p.add_argument('--parts',default='parts');p.add_argument('--output',default='reports');args=p.parse_args()
    report,inventory=aggregate(args.parts)
    out=pathlib.Path(args.output);out.mkdir(exist_ok=True)
    (out/'complete-prelaunch-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (out/'all-322-months-file-metadata.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    lines=['# JARVIS v0.93 上線前完整缺口盤點','',
      '排程啟動：BLOCKED（五條正式處理路徑尚未接妥）。資料發布：BLOCKED（未驗證資料）。','',
      f"本輪回歸：{report['regression']['tests_run']} 項；真實檔案樣本：4 個月份；完整中繼資料盤點：322 個月份／1,288 個來源月份組合。",
      '歷史缺值屬待補資料，不要求下載器先完成所有歷史資料才能啟動。','',
      '| 項目 | 目前狀態 | 尚需完成 |','|---|---|---|']
    for g in report['remaining_acceptance']:lines.append('| '+g['id']+' | '+g['status']+' | '+g['requirement']+' |')
    lines+=['','## 本輪實際量測','', '```json',json.dumps({'backlog':report['historical_backlog'],'native':report['native_samples'],'sandbox':report['sandbox_recovery']},ensure_ascii=False,indent=2),'```','',
      '上述沙盒恢復測試使用真實 GitHub CAS 與 Drive 測試檔；不代表五條正式流程已完成串接。']
    (out/'complete-prelaunch-audit.md').write_text('\n'.join(lines)+'\n')
    print('COMPLETE_PRELAUNCH_AUDIT '+json.dumps({'tests_run':report['regression']['tests_run'],'inventory':inventory['counts'],
          'operational_launch':report['operational_launch'],'data_publication':report['data_publication'],
          'remaining_acceptance':[g['id'] for g in report['remaining_acceptance']],
          'sandbox_recovery_pass':recovery_pass(report['sandbox_recovery']),'production_data_writes':0},sort_keys=True),flush=True)

def recovery_pass(r):
    return r.get('actual_cross_job_resume') is True and r.get('actual_github_cas_collision_winners')==1 and r.get('immutable_payload_readback') is True

if __name__=='__main__':main()
