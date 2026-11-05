"""2026-09 official TWSE/TPEx raw -> Silver price Parquet candidate, immutable Bronze."""
import os,json,zipfile,io,re,hashlib,datetime as dt,decimal,collections,pathlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa, pyarrow.parquet as pq
D=decimal.Decimal
MAIN={'TWSE':'16G68HaFVX1Ddmu23xWeexhNDn0DWryet','TPEx':'1xz7SdR0itvatFQ_IaAdpsAw9fN6i-0iu'}
REC=['12lSt3OY0WclDoCc6TAk3peruEW2-K9_r','1kXahDil5I6Mda5SN0XE-LG0bN8LZBm0y']
DEST='1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5'
DAYS=sorted((dt.date(2026,9,1)+dt.timedelta(days=i)).isoformat() for i in range(30) if (dt.date(2026,9,1)+dt.timedelta(days=i)).weekday()<5 and i+1 not in (25,28))
assert len(DAYS)==20
def sha(b):return hashlib.sha256(b).hexdigest()
def num(s):
 s=str(s).strip().replace(',','')
 if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',s):return None
 n=D(s);return n if n.is_finite() else None
def svc():
 c=Credentials(token=None,refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],client_id=os.environ['GOOGLE_CLIENT_ID'],client_secret=os.environ['GOOGLE_CLIENT_SECRET'],token_uri='https://oauth2.googleapis.com/token',scopes=['https://www.googleapis.com/auth/drive']);c.refresh(Request())
 return build('drive','v3',credentials=c,cache_discovery=False)
def raw(s,id):return s.files().get_media(fileId=id).execute()
def raws(s,source):
 z=zipfile.ZipFile(io.BytesIO(raw(s,MAIN[source])))
 if z.testzip() is not None:raise ValueError('MAIN_ZIP_CRC')
 m=json.loads(z.read('manifest.json'))
 docs={}
 family='prices_indices_' if source=='TWSE' else 'prices_'
 for u in m['units']:
  if not u['name'].startswith(family) or not u.get('date') or not u.get('file'):continue
  name=u['file'].split('/')[-1];data=z.read(name)
  if sha(data)!=u['sha256']:raise ValueError('MAIN_SOURCE_SHA')
  if u['date'] in docs:raise ValueError('DUPLICATE_DATE')
  docs[u['date']]=(data,MAIN[source],name,sha(data))
 if source=='TPEx':
  for id in REC:
   z=zipfile.ZipFile(io.BytesIO(raw(s,id)))
   if z.testzip() is not None:raise ValueError('REPAIR_ZIP_CRC')
   for name in z.namelist():
    x=re.search(r'prices_(2026-09-\d\d)\.raw$',name)
    if not x:continue
    day=x.group(1);data=z.read(name)
    if day in docs:
     if sha(data)!=docs[day][3]:raise ValueError('REPAIR_CONFLICT')
    else:docs[day]=(data,id,name,sha(data))
 if sorted(docs)!=DAYS:raise ValueError('OFFICIAL_20_DAY_SCOPE_INCOMPLETE '+source+str(sorted(set(DAYS)-set(docs))))
 return docs
def convert(s,source):
 docs=raws(s,source);records=[];errs=[];seen=set()
 mp=({'id':'證券代號','name':'證券名稱','open':'開盤價','high':'最高價','low':'最低價','close':'收盤價','shares':'成交股數','amount':'成交金額'} if source=='TWSE' else
     {'id':'代號','name':'名稱','open':'開盤','high':'最高','low':'最低','close':'收盤','shares':'成交股數','amount':'成交金額(元)'})
 for day,(blob,zipid,member,hashval) in sorted(docs.items()):
  obj=json.loads(blob.decode('utf-8-sig'))
  matches=[t for t in obj.get('tables',[]) if ('每日收盤行情' if source=='TWSE' else '上櫃股票行情') in str(t.get('title',''))]
  if len(matches)!=1:raise ValueError('AMBIGUOUS_OFFICIAL_PRICE_TABLE '+day)
  tab=matches[0];columns={f:i for i,f in enumerate(tab['fields'])}
  if not all(v in columns for v in mp.values()):raise ValueError('OFFICIAL_SCHEMA_CHANGE '+day)
  for position,row in enumerate(tab['data']):
   if len(row)!=len(columns):raise ValueError('ROW_WIDTH_MISMATCH '+day)
   code=str(row[columns[mp['id']]]).strip()
   if not re.fullmatch(r'\d{4}',code):continue
   key=(day,code)
   if key in seen:raise ValueError('DUPLICATE_STOCK_DAY '+str(key))
   seen.add(key)
   v={k:row[columns[col]] for k,col in mp.items()}
   prices=[num(v[k]) for k in ('open','high','low','close')]
   volume=num(v['shares']);amount=num(v['amount'])
   if volume is not None and volume<0 or amount is not None and amount<0:raise ValueError('NEGATIVE_VOLUME_OR_AMOUNT')
   valid=all(x is not None for x in prices)
   if valid and not(prices[2]<=prices[0]<=prices[1] and prices[2]<=prices[3]<=prices[1]):raise ValueError('OHLC_LOGIC_ERROR')
   status='NUMERIC_OHLC' if valid else 'NONNUMERIC_OHLC_PENDING_CLASSIFICATION'
   if not valid:errs.append(dict(date=day,stock_id=code,volume=str(volume),native=[str(v[k]) for k in ('open','high','low','close')]))
   records.append({'trade_date':dt.date.fromisoformat(day),'stock_id':code,'market':'TSE' if source=='TWSE' else 'OTC',
      'name':str(v['name']).strip(),'open':prices[0],
      'high':prices[1],'low':prices[2],
      'close':prices[3],
      'volume_shares':int(volume) if volume is not None and volume==volume.to_integral_value() else None,
      'turnover_億元':amount/D('100000000') if amount is not None else None,
      'raw_ohlc_json':json.dumps({k:v[k] for k in ('open','high','low','close')},ensure_ascii=False),
      'status':status,'source_zip_id':zipid,'source_member':member,'source_sha256':hashval,
      'source_row_index':position,'price_adjustment':'UNADJUSTED','published_at':None,
      'pit_verified':False,'silvertime_scope':'CANDIDATE_2026_09'})
 records.sort(key=lambda x:(x['trade_date'],x['stock_id']))
 assert len({(x['trade_date'],x['stock_id']) for x in records})==len(records)
 assert len(set(x['trade_date'] for x in records))==20
 table=pa.Table.from_pylist(records)
  assert pa.types.is_decimal(table.schema.field('open').type)
  assert pa.types.is_decimal(table.schema.field('turnover_億元').type)
  assert pa.types.is_date32(table.schema.field('trade_date').type)
 payload=io.BytesIO();pq.write_table(table,payload,compression='zstd')
 data=payload.getvalue();assert pq.read_table(io.BytesIO(data)).num_rows==len(records)
 return data,records,errs
def save(s,folder,name,data):
 found=s.files().list(q=f"'{folder}' in parents and name = '{name}' and trashed = false",fields='files(id,name)',pageSize=50).execute()['files']
 if len(found)>1:raise ValueError('DUPLICATE_DESTINATION_NAME')
 if found:
  if sha(raw(s,found[0]['id']))!=sha(data):raise ValueError('EXISTING_DESTINATION_MISMATCH')
  return found[0]['id']
 md={'name':name,'parents':[folder]}
 obj=s.files().create(body=md,media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype='application/octet-stream',resumable=True),fields='id').execute()
 if sha(raw(s,obj['id']))!=sha(data):raise ValueError('DESTINATION_READBACK_SHA_MISMATCH')
 return obj['id']
def main():
 s=svc();parents=s.files().list(q=f"'{DEST}' in parents and name = '2026-09_CANDIDATE_98_GATE' and trashed = false",fields='files(id,mimeType)',pageSize=50).execute()['files']
 if len(parents)>1:raise ValueError('AMBIGUOUS_SILVER_MONTH_FOLDER')
 folder=parents[0]['id'] if parents else s.files().create(body={'name':'2026-09_CANDIDATE_98_GATE','mimeType':'application/vnd.google-apps.folder','parents':[DEST]},fields='id').execute()['id']
 out=pathlib.Path('v095_silver_202609');out.mkdir(exist_ok=True)
 for source in ('TWSE','TPEx'):
  data,records,errors=convert(s,source)
  name=f'JARVIS_v095_SILVER_202609_{source}_OHLCV_CANDIDATE_R2.parquet'
  drive_id=save(s,folder,name,data)
  report={'source':source,'period':'2026-09','market':'TSE' if source=='TWSE' else 'OTC',
   'dates':len(set(x['trade_date'] for x in records)),'rows':len(records),
   'numeric_ohlc_rows':len(records)-len(errors),'nonnumeric_rows':len(errors),
   'numeric_ohlc_rate':(len(records)-len(errors))/len(records),
   'positive_volume_nonnumeric':sum(1 for x in errors if num(x['volume']) is not None and num(x['volume'])>0),
   'official_source_members':20,'parquet_drive_id':drive_id,'parquet_sha256':sha(data),
   'destination_folder':folder,'price_unit':'NTD/share','turnover_unit':'億元',
   'published_at':'UNKNOWN','pit_verified':False,'status':'SILVER_CANDIDATE_ONLY',
   'gold_allowed':False,'production_release_approved':False,
   'pending':['classify official nonnumeric OHLC','verify per-source Silver correctness using approved 98 percent measurement','verify publication time and historical identity'],
   'exception_examples':errors[:20]}
  qa=save(s,folder,f'JARVIS_v095_SILVER_202609_{source}_QA_R2.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
  report['qa_drive_id']=qa
  (out/(source+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
  print(json.dumps({k:report[k] for k in ('source','dates','rows','numeric_ohlc_rows','nonnumeric_rows','numeric_ohlc_rate','parquet_drive_id','qa_drive_id','status')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
