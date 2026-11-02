"""Build a traceable document-based issue ledger; never changes live task state.
Run from repository root. Source evidence stays immutable and retains namespaces.
"""
from pathlib import Path
import json,re,hashlib,csv,subprocess
ROOT=Path.cwd(); OUT=ROOT/'docs/issue-ledger/20261102';OUT.mkdir(parents=True,exist_ok=True)
BASE=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
REPO='danny541690/C1-RAW-DOWNLOADER';DATE='2026-11-02'
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def url(p):return f'https://github.com/{REPO}/blob/{BASE}/{p}'
def sources_in(text):
 names={'TWSE':['TWSE','證交所'],'TPEx':['TPEx','櫃買'],'MOPS':['MOPS','觀測站','公開資訊'],'TDCC':['TDCC','集保'],'TAIFEX':['TAIFEX','期交所'],'NDC':['NDC','國發會'],'FinMind':['FinMind']}
 found=[s for s,aliases in names.items() if any(a.lower() in text.lower() for a in aliases)]
 return '/'.join(found) or '跨來源／系統'
def typ(text):
 for words,name in [(['invalid_grant','憑證','授權'],'認證／授權'),(['CAS','PUSH','派送','ACK','workflow','YAML'],'排程／持久化'),(['日期','PIT','vintage'],'日期／可得時間'),(['欄','編碼','bytes','OHLC'],'格式／欄位／內容'),(['空回','空表','母體','覆蓋','完整率'],'適用性／缺失待查')]:
  if any(w.lower() in text.lower() for w in words):return name
 return '其他／治理'
issues=[]; events=[]; sources=[]
previous_events=json.loads((OUT/'events.json').read_text()) if (OUT/'events.json').exists() else [e for page in sorted((OUT/'events').glob('part-*.json')) for e in json.loads(page.read_text())]
legacy_links=json.loads((OUT/'legacy-sources/index.json').read_text())
def add(i,title,rawstatus,finding,action,evidence,asof,scope='歷史紀錄；非即時狀態',related='',count=None):
 if rawstatus.startswith('FIXED') or rawstatus.startswith('RECONCILED'):status='指定範圍已修；資料閉環未全面確認'
 elif rawstatus.startswith(('OPEN','BLOCK','NOT_')):status='待處理／待確認'
 else:status=rawstatus
 issues.append({'issue_id':i,'source':sources_in(title+' '+finding),'category':typ(title+' '+finding),'title':title,'tracking_status':status,'original_status':rawstatus,'finding':finding,'resolution_or_next_action':action,'evidence':evidence,'evidence_as_of':asof,'scope_limit':scope,'related_ids':related,'affected_count':count,'owner':'未指定','next_review_date':'待安排','closure_evidence':'未核定；不得由程式修正推定全資料修復'})

# Parse the human maintained I01-I34 table, not the older machine registry alone.
p='docs/raw-governance/20261029/03_問題追蹤表.md'
for line in (ROOT/p).read_text().splitlines():
 m=re.match(r'^\|\s*(I\d+)\s*\|',line)
 if not m:continue
 c=[x.strip() for x in line.strip().strip('|').split('|')]
 if len(c)<4:continue
 add('RAW-'+c[0],c[2],c[1],c[2],c[3],url(p), '2026-10-30（來源R18／歷史）',related=c[4] if len(c)>4 else '')
e=json.loads((ROOT/'docs/raw-governance/20261031/evidence_registry.json').read_text())
for k in e['incidents']:
 ident,title=k['id_and_keyword'].split(' ',1)
 related=','.join('RAW-'+x for x in sorted(set(re.findall(r'I\d+',k['evidence_locator']))))
 add('KB-'+ident,title,'HISTORICAL_REVIEW',k['finding'],k['handling_and_limit'],url('docs/raw-governance/20261031/02_實測經驗與故障處理.md')+' ; '+k['evidence_locator'],'2026-10-31',related=related)
for o in e['open_items']:
 ident,title=o['id'].split(' ',1)
 add('OPEN-'+ident,title,'OPEN_REVIEW',o['state'],o['next_action'],url('docs/raw-governance/20261031/03_未結事項與跨對話接續.md'),'2026-10-31')
# Explicitly dated latest-report groups. Counts are report snapshot units, not distinct root causes.
latest='docs/raw-governance/20261102/12_收盤跨欄原件修復與未解決項分流.md'
cases=[
('TPEx-ROW_WIDTH','TPEx 收盤價跨欄導致欄位錯移','部分原件已修復','原群507；按報告補回3件推算約504待重驗（507-3），非本次逐件複核、非即時值，未宣稱全群修好。','依實際colspan展開收盤與漲跌；原件SHA與內容重驗後PROMOTE；來源HTTP不增加。',504,'KB-K25,RAW-I31'),
('TPEx-EMPTY','TPEx 原空回應','待查','1,202原空回應；不證明歷史不存在。','查官方歷史窗口、路由、替代官方檔；保留原證據。',1202,'KB-K25'),
('TPEx-ERROR_PAGE','TPEx 錯誤頁','待查','38份錯誤頁。','核對端點、日期與來源回應，有限次數補抓。',38,''),
('TPEx-MIXED_BYTES','TPEx 混合替代bytes','待查','131份混合替代bytes。','保留原件；核對編碼與官方替代檔，不忽略錯誤字元。',131,''),
('TPEx-TRUNCATED','TPEx 回應截斷','待查','10份截斷回應。','核對原始長度及完整性，再依額度補抓，不當編碼修復。',10,''),
('TPEx-NO_CODE_HEADER','TPEx 無代碼表頭','待查','6份無代碼表頭。','辨識是否錯頁／schema／適用性，不以忽略欄位放行。',6,''),
('TPEx-MARKET_SCOPE','TPEx 市場範圍不足','待查','2份市場範圍不足。','核對當期市場與證券母體。',2,''),
('TPEx-NAME_REPLACEMENT','TPEx 公司名替代字元','待查','1份公司名含替代字元。','核對官方字型／對照，不猜公司名。',1,''),
('TPEx-RECHECK_EMPTY','TPEx 重查空回應','待查','6份重查仍空回應。','保留嘗試次數；查來源範圍與替代路由。',6,''),
('TWSE-EMPTY_REVIEW','TWSE 空回應未證實例外','待查','152件中2件已取得休市證據後，150件仍待查。','逐日期官方休市／來源適用性證據；空回應不能直接關閉。',150,'RAW-I31'),
('TWSE-CLOSURE','TWSE 兩日期官方休市','已確認例外','2024-07-24、2024-10-03有官方PDF證據；不是下載成功。','只排除這兩個核定日期，其他日期不得推定。',2,''),
('MOPS-ROUTE','MOPS 歷史入口／分區','待查','128件歷史入口／分區問題。','核對_1適用市場及歷史路由，不刪早年缺口。',128,'KB-K08,KB-K09,OPEN-O04'),
('MOPS-NO_COMPANY','MOPS 無公司列','待查','3件無公司列。','檢查當期公司適用性與官方原表。',3,'KB-K09'),
('MOPS-ENCODING','MOPS 編碼／自造字','待查','2件編碼問題；含2004/09 8450自造字。','取得來源字型或官方對照；不猜值。',2,''),
('TDCC-QUEUE','TDCC 尚未處理佇列','排隊工作；不列錯誤','未處理任務不是下載失敗。','保留來源鎖、lease、checkpoint及兩方向輪替。',None,'OPEN-O03,KB-K07')]
for cid,title,status,finding,action,count,rel in cases:add('CUR-'+cid,title,status,finding,action,url(latest),'2026-11-02 09:16 +08:00','固定核准清單的當時快照，非最新live、非全庫統計',rel,count)
add('GOV-REGISTRY-LAG','舊機讀問題清單落後人工問題表','本次彙整已補入','registry.json只有24項，但同版Markdown已列I01-I34。','本帳以I01-I34完整表補入並保留兩個來源，不改動原始登錄。',url(p),'2026-11-02','彙整差異已處理，不等於資料缺失已解決')
# Legacy October QA remains in its own namespace; never reuse as current RAW acceptance.
add('LEGACY-QA006','C1-JARVIS早期QA-006與歷史行情可得性','歷史狀態待重新對帳','10/9 checkpoint記錄TWT53U歷史查詢未驗證、PY-006D/E INCONCLUSIVE。較晚checkpoint另保留在來源檔，不以舊結論覆蓋新狀態。','讀legacy-sources完整checkpoint對應事件後，逐項核對後續證據。',legacy_links['JARVIS_GITHUB_PYTHON_TEST_CHECKPOINT_2026-10-09.md'],'2026-10-09','前代系統知識證據，不匯入前代市場資料／PASS')

# Document evidence events: every paragraph/table row is retained, with line locator.
paths=sorted({p for d in ['docs','reports'] for p in (ROOT/d).rglob('*.md') if 'issue-ledger' not in p.parts})
paths+=sorted((OUT/'legacy-sources').glob('*.md'))
for file in paths:
 rel=file.relative_to(ROOT).as_posix();text=file.read_text();sidh='SRC-'+digest(rel)[:12]
 link=url(rel) if 'legacy-sources' not in rel else legacy_links[file.name]
 match=re.search(r'20\d{6}',rel);docdate=(match[0][:4]+'-'+match[0][4:6]+'-'+match[0][6:]) if match else 'UNKNOWN（見原文）'
 sources.append({'source_id':sidh,'path':rel,'version_date_hint':docdate,'source_sha256':digest(text),'pinned_url':link,'access':'FULL_TEXT_IMPORTED','characters':len(text)})
 heading='文件開頭';block=[];start=1
 def emit():
  if not block:return
  txt='\n'.join(block)
  for offset in range(0,len(txt),8000):
   fragment=txt[offset:offset+8000];refs=','.join(sorted(set(re.findall(r'\b(?:I\d{2}|K\d{2}|O\d{2}|QA-?\d+|PY-\d+[A-Z-]*)\b',fragment))))
   eid='EV-'+digest(rel+'\0'+str(start)+'\0'+str(offset)+'\0'+fragment)[:20]
   events.append({'event_id':eid,'event_kind':'DOCUMENT_EVIDENCE_BLOCK','source_id':sidh,'document_version_date':docdate,'heading':heading,'line_start':start,'related_literal_ids':refs,'source':sources_in(fragment),'text':fragment,'evidence_url':link+('#L'+str(start) if link.startswith('http') else ''),'content_sha256':digest(fragment),'source_version_sha256':digest(text),'status_interpretation':'原文快照；不是已重查的即時狀態'})
 for line_no,line in enumerate(text.splitlines(),1):
  if line.startswith('#'):
   emit();block=[];heading=line.lstrip('# ').strip();start=line_no+1
  elif not line.strip():emit();block=[];start=line_no+1
  else:
   if not block:start=line_no
   block.append(line)
 emit()
# Import structured tests individually as test evidence (not market repair).
reg=json.loads((ROOT/'docs/raw-governance/20261029/registry.json').read_text())
for test in reg['test_results']:
 txt=json.dumps(test,ensure_ascii=False,sort_keys=True)
 events.append({'event_id':'TEST-'+test['id'],'event_kind':'TEST_RESULT_SCOPE_ONLY','source_id':'registry.json','document_version_date':'2026-10-30','heading':test.get('name',''),'line_start':None,'related_literal_ids':test['id'],'source':'跨來源／系統','text':txt,'evidence_url':test.get('run_url') or test.get('evidence') or url('docs/raw-governance/20261029/registry.json'),'content_sha256':digest(txt),'status_interpretation':test.get('status','UNKNOWN')})
# Preserve all prior evidence events; do not erase an old failure after a later fix.
for issue in issues:
 txt=json.dumps(issue,ensure_ascii=False,sort_keys=True)
 events.append({'event_id':'ISSUE-'+digest(txt)[:20],'event_kind':'ISSUE_INDEX_SNAPSHOT','source_id':'unified-ledger','document_version_date':issue['evidence_as_of'],'heading':issue['title'],'line_start':None,'related_literal_ids':issue['issue_id'],'source':issue['source'],'text':txt,'evidence_url':issue['evidence'],'content_sha256':digest(txt),'status_interpretation':issue['tracking_status']})
merged={x['event_id']:x for x in previous_events}
merged.update({x['event_id']:x for x in events})
events=list(merged.values())
assert len({x['issue_id'] for x in issues})==len(issues)
assert len({x['event_id'] for x in events})==len(events)
assert {f'RAW-I{i:02d}' for i in range(1,35)}.issubset(x['issue_id'] for x in issues)
summary={'schema':'JARVIS_UNIFIED_ISSUE_LEDGER_V1','created_date_taipei':DATE,'source_main_sha':BASE,'review_window':['2026-10-01','2026-11-02'],'issue_index_records':len(issues),'evidence_events':len(events),'source_documents':len(sources),'raw_modified':False,'production_state_modified':False,'coverage':'Known tracked repository documents plus five early-October legacy references; NOT every Actions run, branch state page or historical chat. No claim of exhaustive monthly reconciliation.','counts_semantics':'Issue index entries include aliases and historical namespaces; not a count of unique root causes or missing market files. Evidence blocks are document paragraphs/table rows, not individual HTTP requests.','latest_counts_as_of':'2026-11-02 09:16 +08:00; not live'}
for name,obj in [('issues.json',issues),('events.json',events),('sources.json',sources),('manifest.json',summary)]:
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
for name,data in [('issues.csv',issues),('events.csv',events),('sources.csv',sources)]:
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
print(json.dumps(summary,ensure_ascii=False))
