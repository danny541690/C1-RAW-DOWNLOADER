"""One command runs implemented eleven-slot preflight tests and reports gaps."""
import argparse,contextlib,datetime,hashlib,io,json,time,unittest
from pathlib import Path
import yaml

PATTERNS=('test_seven_source_plan.py','test_source_partition.py','test_source_migration_and_scope.py',
          'test_source_closed_loop_preflight.py','test_source_coordination.py','test_source_git_store.py','test_acceptance_scheduler.py','test_acceptance_state.py','test_tdcc_download_v4.py')
BLOCKERS={
 'source_executors':'BLOCKED_NOT_INTEGRATED',
 'distributed_fencing_and_immediate_continuation':'BLOCKED_NOT_INTEGRATED',
 'live_eleven_slot_fetch_save_reverify':'NOT_RUN',
 'one_time_legacy_shutdown_and_state_migration':'NOT_RUN',
 'real_rate_limits_and_three_day_throughput':'NOT_RUN'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();start=time.monotonic()
 root=Path(__file__).resolve().parent.parent;loader=unittest.TestLoader();suite=unittest.TestSuite()
 for pattern in PATTERNS:suite.addTests(loader.discover(str(root/'tests'),pattern=pattern))
 log=io.StringIO()
 with contextlib.redirect_stdout(io.StringIO()):result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 errors=[];files=[]
 for path in sorted((root/'.github/workflows').glob('jarvis-seven-*-preview.yml')):
  files.append(path.name)
  try:
   doc=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
   if set(doc['on'])!={'workflow_dispatch'} or doc['permissions']!={'contents':'read'}:
    raise ValueError('PREVIEW_EXECUTION_BOUNDARY')
   if 'secrets.' in path.read_text():raise ValueError('UNEXPECTED_PREVIEW_SOURCE_SECRET')
  except Exception as exc:errors.append(dict(file=path.name,error=type(exc).__name__))
 if len(files)!=11:errors.append(dict(error='EXPECTED_ELEVEN_PREVIEWS'))
 a.out.mkdir(parents=True,exist_ok=True)
 test_result=dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped))
 passed=result.wasSuccessful() and not errors
 report=dict(schema='JARVIS_ELEVEN_PREFLIGHT_V4',checked_at_taipei=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
  implemented_tests_passed=passed,tests=test_result,yaml_files=len(files),yaml_errors=errors,
  readiness=BLOCKERS,deployment_ready=False,market_requests=0,production_writes=0,
  source_environment='Fake official HTTP; native TDCC parser; real local files, bare Git and transactional SQLite shared by threads and separate processes; not live Drive or GitHub distributed CAS',
  elapsed_seconds=round(time.monotonic()-start,3),cutover_strategy='ONE_TIME_SWITCH_NO_DUAL_OPERATION',
  existing_online_schedules_changed=False,
  input_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set((root/'scripts').glob('v093_source_*.py'))|set((root/'scripts').glob('v093_tdcc*.py'))|{root/'config/v093_seven_source_design.json'}|{root/'tests'/name for name in PATTERNS})})
 (a.out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 (a.out/'tests.log').write_text(log.getvalue())
 (a.out/'README.md').write_text('# 十一工作槽合併測試\n\n'+f"已實作測試 {'PASS' if passed else 'FAIL'}：{test_result}。十一份預覽YAML驗證錯誤 {len(errors)}。\n\n"+
  '來源回應為fixture，檔案與Git為本機實際操作；不是新十一條的真實Drive閉環。\n\n'+
  '| 上線門檻 | 狀態 |\n|---|---|\n'+''.join(f'| {k} | {v} |\n' for k,v in BLOCKERS.items())+
  '\n正式上線仍阻擋。保存舊狀態後一次停用舊觸發，再啟動新十一條；本次測試沒有停用任何線上排程。\n')
 print(json.dumps(report,ensure_ascii=False))
 raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
