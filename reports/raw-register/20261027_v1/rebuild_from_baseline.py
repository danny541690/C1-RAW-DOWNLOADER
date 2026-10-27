import csv,gzip,pathlib,json,hashlib,collections,datetime
B=pathlib.Path('baseline');O=pathlib.Path('final');(O/'units').mkdir(exist_ok=True)
def read(n):return csv.DictReader(open(B/n,encoding='utf-8-sig',newline=''))
recent={(r['來源'],r['待補月份'],r['單元ID']):r for r in read('21_來源重查與品質狀態核對.csv')}
orig=read('01_下載清單.csv').fieldnames
extra=['快照ID','任務ID','年份','檢查狀態','已下載','基本格式存檔通過','已保存待內容驗證','未下載','取得缺口待核實','尚未發布或未到期','明列品質問題','問題代碼','RAW_SHA256','原件參照','RAW帳本時間_台灣','檢查帳本時間_台灣','未補日期數','計畫母體性質']
heads=extra+['來源','月份','單元ID','資料集','期間','代碼','RAW狀態','補正狀態','錯誤','補正錯誤','證據連結','補正證據連結','未補日期','開放檢查','官方缺口','原始日期語意','補充不關閉官方缺口','預期代碼','取得代碼','嘗試次數','補正嘗試次數']
files={};ws={};agg=collections.defaultdict(collections.Counter);seen=set();ic=collections.Counter()
def arr(v):
 try:return json.loads(v or '[]')
 except:return []
def tai(v):
 try:return datetime.datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
 except:return v
for name in ['01_下載清單.csv','08_TDCC尚未嘗試候選.csv']:
 for r in read(name):
  src=r['來源'];month=r['月份'];key=(src,month,r['單元ID']);v=recent.get(key,{})
  task=hashlib.sha256('|'.join(key).encode()).hexdigest()[:20];assert task not in seen;seen.add(task)
  raw=v.get('本次RAW狀態') or r['RAW狀態'];s=v.get('本次檢查狀態') or r.get('補正狀態','');sha=v.get('RAW_SHA256') or r.get('SHA256','');ref=v.get('原始檔參照') or r.get('原檔參照','')
  down=bool(sha and ref and raw in ['SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','RAW_DOWNLOADED_UNVERIFIED']);basic=down and raw!='RAW_DOWNLOADED_UNVERIFIED';pending=down and not basic;notdue=raw=='NOT_YET_PUBLISHED_IN_VERIFIED_SOURCE'
  unfilled=arr(r.get('未補日期'));quality=bool('OPEN_QUALITY_ITEMS' in s or unfilled or (src=='NDC' and arr(r.get('開放檢查'))))
  if quality:code='Q1'
  elif 'SOURCE_BACKOFF' in s:code='Q2'
  elif s in ['UNRESOLVED_OFFICIAL_ROUTE','OFFICIAL_ROUTE_NOT_FOUND']:code='Q3'
  elif s in ['UNRESOLVED_ATTEMPT_LIMIT','UNRESOLVED_RETRY_CYCLES_EXHAUSTED']:code='Q4'
  elif 'SOURCE_LIMIT' in s or raw=='FINMIND_PROVIDER_WAIT':code='Q5'
  elif notdue:code='P1'
  elif raw=='PLAN_ONLY_NOT_ATTEMPTED':code='O7'
  elif r.get('分類')=='遺失快照待查證':code='O5'
  elif raw=='OFFICIAL_PERIOD_NOT_PROVIDED' or s=='OFFICIAL_PERIOD_NOT_PROVIDED' or r.get('分類')=='來源提供界限':code='O2'
  elif s=='SOURCE_CONTENT_INCOMPLETE' or raw=='RAW_RESPONSE_REVIEW_HOLD' and r.get('分類')=='品質或解析待驗證':code='O4'
  elif raw in ['UNRESOLVED','FINMIND_GAP_UNRESOLVED'] and not s:code='O9'
  elif s in ['WAIT_SHARED_SOURCE_WINDOW','SOURCE_CHECK_REQUEST_INTENT','UNRESOLVED_TIME_LIMIT'] or (raw in ['RETRY_WAIT','SOURCE_CIRCUIT_WAIT','REQUEST_INTENT','REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED'] and r.get('分類')!='來源空白待核實'):code='O6'
  elif r.get('分類')=='來源空白待核實':code='O1'
  elif s=='CONTENT_CHECK_PASS' and down:code='P0'
  elif pending:code='O8'
  elif down:code='P0'
  else:code='O9'
  a=agg[(src,month)];a['已知計畫總數']+=1
  for k,val in {'已下載':down,'基本格式存檔通過':basic,'已保存待內容驗證':pending,'未下載':not down,'取得缺口待核實':not down and not notdue,'尚未發布或未到期':notdue,'明列品質問題':quality,'已知待處理聯集':code.startswith(('Q','O')),'未補日期數':len(unfilled)}.items():a[k]+=int(val)
  a[code]+=1;ic[code]+=1
  z={**r,**dict(zip(extra,['JARVIS_RAW_REGISTER_20261027_V1',task,month[:4],s,int(down),int(basic),int(pending),int(not down),int(not down and not notdue),int(notdue),int(quality),code,sha,ref,v.get('RAW帳本更新_台灣') or tai(r.get('收據更新UTC','')),v.get('檢查帳本更新_台灣') or tai(r.get('補正更新UTC','')),len(unfilled),'TDCC未核准候選母體' if name.startswith('08') else '已記錄查詢單元；非全庫應有觀察值']))}
  if src not in files:
   files[src]=gzip.open(O/'units'/f'{src}_units.csv.gz','wt',encoding='utf-8-sig',newline='');ws[src]=csv.DictWriter(files[src],fieldnames=heads,extrasaction='ignore');ws[src].writeheader()
  ws[src].writerow(z)
for f in files.values():f.close()
tot=sum(agg.values(),collections.Counter());print('units',len(seen),'counts',tot,'issues',ic)
(O/'recomputed.json').write_text(json.dumps({'counts':dict(tot),'issues':dict(ic),'unique_units':len(seen)},ensure_ascii=False,indent=2))
# Restore the previously verified, immutable aggregate tables from the surviving workbook.
for i,n in [(2,'來源年份月份對帳.csv'),(3,'來源年份對帳.csv'),(4,'來源總覽.csv'),(5,'問題分類字典.csv')]:
 rows=json.load(open(O/f'sheet{i}.json'));rows=rows[1:]
 with open(O/n,'w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows(rows)
# Report any disagreement; never silently change the published aggregate counts.
expected=list(csv.DictReader(open(O/'來源年份月份對帳.csv',encoding='utf-8-sig')));errors=[]
for e in expected:
 a=agg[(e['來源'],e['月份'])]
 for k in ['已知計畫總數','已下載','基本格式存檔通過','已保存待內容驗證','未下載','明列品質問題','Q1','Q2','Q3','Q4','Q5','已知待處理聯集']:
  if a[k]!=int(e[k]):errors.append([e['來源'],e['月份'],k,a[k],int(e[k])])
(O/'rebuild_differences.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2));print('differences',len(errors),errors[:12])
