"""Reconcile the coordinator and three unique worker reports; never approve RAW."""
import argparse
import datetime
import json
import os
from pathlib import Path

SCHEMA = 'JARVIS_ACCEPTANCE_SCHEDULER_SUMMARY_V1'
LANES = {'inventory', 'worker-0', 'worker-1', 'worker-2'}


def combine(summaries, inventory_job, content_job):
    errors, reports = [], {}
    for summary in summaries:
        lane = summary.get('lane')
        if summary.get('schema') != 'JARVIS_ACCEPTANCE_SCHEDULER_V1' or lane not in LANES:
            errors.append('UNKNOWN_REPORT_SCHEMA_OR_LANE')
            continue
        if lane in reports:
            errors.append('DUPLICATE_LANE:' + lane)
            continue
        reports[lane] = summary
        if summary.get('approved_scopes') != [] or summary.get('production_writes') != 0 or summary.get('source_downloads') != 0:
            errors.append('UNEXPECTED_RELEASE_OR_SOURCE_WRITE:' + lane)
        count = summary.get('slice', {}).get('inspected')
        if type(count) is not int or count < 0:
            errors.append('INVALID_INSPECTION_COUNT:' + lane)
    missing = sorted(LANES - reports.keys())
    if missing:
        errors.append('MISSING_LANES:' + ','.join(missing))
    if inventory_job != 'success' or content_job != 'success':
        errors.append('UPSTREAM_JOB_NOT_SUCCESSFUL')
    result = 'INCOMPLETE'
    if not errors:
        inventory = reports['inventory']['slice']['status']
        workers = [reports[f'worker-{i}']['slice']['status'] for i in range(3)]
        if inventory == 'INVENTORY_COMPLETE' and all(s == 'SLICE_COMPLETE_NOT_FULL_ACCEPTANCE' for s in workers):
            result = 'PARTIAL_EVIDENCE_NOT_FULL_ACCEPTANCE'
        elif inventory == 'INVENTORY_INCOMPLETE' and all(s == 'WAITING_FOR_INVENTORY' for s in workers):
            result = 'WAITING_FOR_INVENTORY'
        else:
            errors.append('INCONSISTENT_OR_BLOCKED_LANE_STATUS')
    progress_reports=[s['progress'] for lane,s in reports.items() if lane!='inventory' and s.get('progress') and s.get('progress_recomputed_this_run')]
    metrics=('required_items','checked_items','partial_content_items','content_blocked_items','repaired_content_blockers','confirmed_exception_items','completed_items','pending_items','unchecked_items')
    progress={k:sum(p[k] for p in progress_reports) for k in metrics} if len(progress_reports)==3 else None
    return dict(schema=SCHEMA, pipeline_status=result,progress=progress,progress_available_workers=len(progress_reports), errors=errors, missing_lanes=missing,
                reported_workers=len(set(reports) - {'inventory'}),
                inspected_this_run=sum(s['slice']['inspected'] for s in reports.values()
                                       if type(s.get('slice', {}).get('inspected')) is int
                                       and s['slice']['inspected'] >= 0),
                lanes={lane: s.get('slice') for lane, s in reports.items()},
                full_groups_passed=0, approved_scopes=[], production_writes=0,
                note='Worker evidence only; no approved historical universe or full eight-group acceptance')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--journal', type=Path)
    args = parser.parse_args()
    summaries=[]
    for path in sorted(args.reports.rglob('summary.json')):
        try:
            value=json.loads(path.read_text())
            summaries.append(value if isinstance(value,dict) else {})
        except (ValueError,OSError):
            summaries.append({})  # Invalid/missing lanes become a persisted INCOMPLETE report.
    result = combine(summaries, os.environ.get('INVENTORY_RESULT'), os.environ.get('CONTENT_RESULT'))
    result['run_id'] = os.environ.get('GITHUB_RUN_ID')
    result['run_attempt'] = os.environ.get('GITHUB_RUN_ATTEMPT')
    result['checked_at_taipei'] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    result['workflow_sha'] = os.environ.get('GITHUB_SHA')
    result['run_url'] = (os.environ.get('GITHUB_SERVER_URL','https://github.com') + '/' + os.environ.get('GITHUB_REPOSITORY','') + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID',''))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if args.journal:
        from scripts.v093_acceptance_scheduler import save
        save(args.journal / 'summary.json.gz', result)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('# JARVIS 合併驗收\n\n')
            stream.write(f"本輪狀態：{result['pipeline_status']}。\n\n")
            stream.write(f"收到不同內容工作：{result['reported_workers']}/3；本輪內容檢查：{result['inspected_this_run']} 筆。\n\n")
            if result['progress']:
                stream.write('| 項目 | 數量 |\n|---|---:|\n')
                labels={'required_items':'已下載登錄應檢查','checked_items':'已檢查（含部分與阻擋）','partial_content_items':'部分內容證據','content_blocked_items':'內容阻擋','repaired_content_blockers':'已修復內容阻擋','confirmed_exception_items':'已確認例外','completed_items':'整項完成','pending_items':'尚待補齊驗收','unchecked_items':'其中未檢查'}
                for key,label in labels.items():stream.write(f"| {label} | {result['progress'][key]:,} |\n")
                stream.write('\n僅計已下載登錄範圍；已檢查與待辦可重疊，未核准全庫母體分母。\n\n')
            stream.write('八組完整驗收仍未通過，正式發布核准範圍為0。缺少母體、契約、PIT及必要檢查器持續待核。\n\n')
            if result['errors']:
                stream.write('流程缺失：' + ', '.join(result['errors']) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    if result['errors']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
