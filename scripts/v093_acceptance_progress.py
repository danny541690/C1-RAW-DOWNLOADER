"""Count scoped progress without equating partial content checks with release."""
import csv,gzip,json
from pathlib import Path

PARTIAL={'REMAINING_RULES_OPEN','ESB_RAW_ONLY_RULES_OPEN'}
CHECKED=PARTIAL|{'CONTENT_BLOCKED'}

def build_progress(queue_path, signatures, groups, prior_reports=()):
    previous={}
    # Reports must be passed in chronological order; latest observation wins.
    for path in prior_reports:
        report=json.loads(Path(path).read_text())
        if report.get('schema')!='JARVIS_INCREMENTAL_PROGRESS_V1':
            raise ValueError('PROGRESS_SCHEMA_MISMATCH')
        previous.update(report['checked_items'])
    items={};total=0;reused=0;newly_checked=0;newly_repaired=0;invalidated=0
    queues={}
    with gzip.open(queue_path,'rt',encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            total+=1;key=row['task_key'];status=row['status']
            queues[row['queue']]=queues.get(row['queue'],0)+1
            old=previous.get(key);signature=signatures.get(row['source'])
            same=bool(old and signature and old['checker_signature']==signature and old['raw_sha256']==row['raw_sha256'])
            if status in CHECKED:
                fixed=bool(old and old['status']=='CONTENT_BLOCKED' and status in PARTIAL)
                newly_repaired+=int(fixed)
                newly_checked+=int(not same)
                items[key]=dict(source=row['source'],period=row['period'],raw_sha256=row['raw_sha256'],
                    checker_signature=signature,status=status,repaired_content_blocker=bool(fixed or (same and old.get('repaired_content_blocker'))))
            elif same:
                items[key]=old;reused+=1
            elif old:
                invalidated+=1
    partial=sum(x['status'] in PARTIAL for x in items.values())
    blocked=sum(x['status']=='CONTENT_BLOCKED' for x in items.values())
    repaired=sum(bool(x['repaired_content_blocker']) for x in items.values())
    # No full-scope approval/exception executor exists here. Never infer an
    # exception from empty input, source errors, or "not in local cache".
    return dict(schema='JARVIS_INCREMENTAL_PROGRESS_V1',scope='FROZEN_REGISTER_TASKS_NOT_APPROVED_GLOBAL_UNIVERSE',
        required_items=total,checked_items_count=len(items),partial_content_items=partial,
        repaired_items=repaired,confirmed_exception_items=0,completed_items=0,pending_items=total,
        unchecked_items=total-len(items),content_blocked_items=blocked,newly_checked_items=newly_checked,
        newly_repaired_items=newly_repaired,reused_prior_checked_items=reused,invalidated_prior_items=invalidated,
        current_batch_queues=queues,checked_items=items,
        groups=[dict(id=g['id'],name=g['name'],required_rules=len(g['rules']),completed_rules=0,
            pending_rules=len(g['rules']),partial_evidence_records=sum(o.get('artifact_records',o.get('units',0)) for o in g['observations']),
            remaining=g['remaining']) for g in groups],
        definitions=dict(checked='已執行部分內容檢查，包含仍有阻擋者；可與待處理重疊',
            repaired='先前內容阻擋已重驗解除；仍可能有其他規則待完成',
            exceptions='僅計有查證證據且已核准的例外；目前未接入例外核准器',
            pending='尚未整項結案；含已部分檢查與尚未檢查，不等於全部都是錯誤'),
        formal_release='BLOCKED',approved_global_denominator=False)

def render_progress(p):
    rows=[('登錄應處理項目',p['required_items']),('已檢查（部分內容）',p['checked_items_count']),
          ('已修復內容阻擋',p['repaired_items']),('已確認例外',p['confirmed_exception_items']),
          ('已整項完成',p['completed_items']),('尚待處理／補證據',p['pending_items']),
          ('其中尚未檢查',p['unchecked_items']),('其中內容阻擋',p['content_blocked_items'])]
    lines=['# 分批驗收進度','','| 項目 | 數量 |','|---|---:|']+[f'| {k} | {v:,} |' for k,v in rows]
    lines+=['','已檢查與尚待處理可重疊；登錄筆數不是已核准的全庫完整性分母。',
            '已修復僅指有前後重驗證據的內容阻擋解除，不代表所有規則通過。','',
            f"本次首次／版本變更後檢查 {p['newly_checked_items']}；本次解除內容阻擋 {p['newly_repaired_items']}；沿用既有檢查 {p['reused_prior_checked_items']}。",'',
            '| 組別 | 應完成規則 | 已完成 | 未完成 |','|---|---:|---:|---:|']
    lines += [f"| {g['id']} {g['name']} | {g['required_rules']} | {g['completed_rules']} | {g['pending_rules']} |" for g in p['groups']]
    return '\n'.join(lines)+'\n'
