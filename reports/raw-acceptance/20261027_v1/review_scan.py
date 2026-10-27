import csv,gzip,pathlib,json,collections,re,importlib.util
O=pathlib.Path('acceptance');a=collections.Counter();ex=collections.defaultdict(list)
def mark(k,u):
 a[k]+=1
 if len(ex[k])<6:ex[k].append({c:u.get(c,'') for c in ['任務ID','來源','月份','單元ID','問題代碼','RAW帳本時間_台灣','檢查帳本時間_台灣']})
def has(v):
 try:return bool(json.loads(v or '[]'))
 except:return bool(v)
for p in pathlib.Path('final/units').glob('*.gz'):
 with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
  for u in csv.DictReader(f):
   a['units']+=1
   if u['已下載']=='1':
    if not re.fullmatch('[0-9a-fA-F]{64}',u['RAW_SHA256']):mark('downloaded_invalid_sha',u)
    if not u['原件參照']:mark('downloaded_missing_reference',u)
    if not u['RAW帳本時間_台灣']:mark('downloaded_missing_capture_timestamp',u)
   if not u['RAW帳本時間_台灣']:mark('raw_timestamp_absent',u)
   if not u['檢查帳本時間_台灣']:mark('check_timestamp_absent',u)
   if u['問題代碼']!='Q1' and has(u['開放檢查']):mark('secondary_quality_flag_outside_Q1',u)
   if u['問題代碼']=='P0' and u['檢查狀態']=='':mark('P0_without_repair_status',u)
   if u['代碼'].startswith('0'):mark('leading_zero_identifier_unit',u)
spec=importlib.util.spec_from_file_location('audit','review/scripts_v093_official_content_audit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw=json.dumps({'fields':['證券代號','開盤價','最高價','最低價','收盤價'],'data':[['2330','100','110','90','105'],['0050','100','50','40','45']]}).encode()
r=m.audit_rows(raw,{'source':'TWSE','category':'prices'})
proof={'fixture':'SYNTHETIC; no actual market records','result':r,'finding':'Mixed table: 2330 checked, leading-zero 0050 OHLC violation not checked; unverified empty. Scope-dependent checker coverage gap, not evidence actual 0050 data wrong.'}
(O/'review_evidence.json').write_text(json.dumps({'baseline':'JARVIS_RAW_REGISTER_20261027_V1','counts':dict(a),'examples':dict(ex),'synthetic_parser_probe':proof,'scope':'All 337023 register units + selected current checker source; no full remote RAW refetch or cell-level revalidation'},ensure_ascii=False,indent=2))
print(dict(a));print(proof)
