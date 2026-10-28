import pathlib,json,datetime
p=pathlib.Path(__file__).parent
rules=json.load(open('esb_contract_work/reports/raw-acceptance/20261027_v1/acceptance_rules.json'))['rules']
assign={
'R01':['G01','G02','G08','M01','A02','D01'],
'R02':['G06','G07','T03','A01'],
'R03':['G09','G10','G22','F01','F02'],
'R04':['G04','G05','G11','G12','T01','T02','M02','A03','D02','N01'],
'R05':['G14','G15'],
'R06':['G13','M03','N02'],
'R07':['G16','G18','G19'],
'R08':['G03','G17','G20','G21']}
ids=[x for a in assign.values() for x in a];assert len(ids)==37 and len(set(ids))==37 and set(ids)=={x['規格ID'] for x in rules}
names=['母體與全量原件','歷史證券日期主鍵','欄位單位契約','完整數值覆蓋','獨立跨來源比對','公告PIT與版本','真實發布與下游','全量復原與時效']
groups=[dict(id=k,name=names[int(k[-2:])-1],primary_rules=v,status='BLOCKED' if k=='R07' else 'UNKNOWN' if k=='R06' else 'PARTIAL',ownership_status='PROPOSED_PRIMARY_OWNER_NOT_RULE_COMPLETION') for k,v in assign.items()]
rows=[dict(rule_id=r['規格ID'],name=r['驗收面向'],primary_group=next(g for g,rr in assign.items() if r['規格ID'] in rr),execution_status='REQUIRES_REAL_DATA_EVIDENCE_NOT_INFERRED_FROM_MAPPING') for r in rules]
obj=dict(plan_version='JARVIS_ACCEPTANCE_ACCELERATION_20261028_V1',status='PLANNED_NOT_FULL_PIPELINE_IMPLEMENTED',created_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),target_history='2000-01-01 through 2026 latest due/published data; future/not-due excluded only with evidence',round_goal=dict(main_full_scope_runs=1,targeted_correction_runs=1,guaranteed_completion=False,rule='Failures and missing evidence remain open; additional runs require explicit new cause'),baseline=dict(full_groups=0,partial=6,unknown=1,blocked=1,last_code_tests_passed=846,last_merged_pr=43,last_merged_commit='ac7cabf928af8929ae7a9a835d29f2192b3f467a',local_content_blocked_files=6,local_content_evidence_records=562,registered_record_count=337281,approved_universe_count=None,approved_release_scopes=0),groups=groups,rule_ownership=rows,stages=[dict(id='P1',name='freeze scope and reconcile remote inventory',depends_on=[]),dict(id='P2',name='read each unique RAW package once and bind SHA',depends_on=['P1']),dict(id='P3',name='run source-specific content/contract/PIT/cross-source checks',depends_on=['P2']),dict(id='P4',name='restore immutable candidate and verify freshness',depends_on=['P2']),dict(id='P5',name='collect all eight group evidence and evaluate release gate',depends_on=['P3','P4']),dict(id='P6',name='publish only qualified scope; readback, downstream consumption and rollback checks',depends_on=['P5'])],proof_states=['PASS','FAIL','UNKNOWN','NOT_APPLICABLE_WITH_EVIDENCE'],missing_checker_state='NOT_IMPLEMENTED_BLOCKED',hard_stops=['scope or denominator unknown','required checker missing','required evidence unknown','input snapshot changed without versioned continuation','payload or evidence SHA mismatch'],resume_key_fields=['source','dataset','logical_unit','period','raw_sha256','universe_version','contract_version','relevant_checker_signature','pit_evidence_digest'],reported_counts_separate=['expected_observations','unique_downloaded_logical_units','downloaded_artifact_versions','content_verified_units','missing_due_units','unknown_units','raw_only_units','approved_scope_units'])
(p/'execution_plan.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2))
lines=['| 規格 | 面向 | 主責組 |','|---|---|---|']+[f"| {r['rule_id']} | {r['name']} | {r['primary_group']} |" for r in rows]
(p/'rule_ownership.md').write_text('# 37 條規格主責分配草案\n\n分配主責不代表實作完成或驗收通過。跨組依賴仍需檢查。\n\n'+'\n'.join(lines)+'\n')
print('37 rules mapped exactly once; plan schema created')
