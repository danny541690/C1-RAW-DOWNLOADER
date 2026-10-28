"""Reconcile the coordinator and three unique worker reports; never approve RAW."""
import argparse
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
    return dict(schema=SCHEMA, pipeline_status=result, errors=errors, missing_lanes=missing,
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
    args = parser.parse_args()
    summaries = [json.loads(p.read_text()) for p in sorted(args.reports.rglob('summary.json'))]
    result = combine(summaries, os.environ.get('INVENTORY_RESULT'), os.environ.get('CONTENT_RESULT'))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('# JARVIS 合併驗收\n\n')
            stream.write(f"本輪狀態：{result['pipeline_status']}。\n\n")
            stream.write(f"收到不同內容工作：{result['reported_workers']}/3；本輪內容檢查：{result['inspected_this_run']} 筆。\n\n")
            stream.write('八組完整驗收仍未通過，正式發布核准範圍為0。缺少母體、契約、PIT及必要檢查器持續待核。\n\n')
            if result['errors']:
                stream.write('流程缺失：' + ', '.join(result['errors']) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    if result['errors']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
