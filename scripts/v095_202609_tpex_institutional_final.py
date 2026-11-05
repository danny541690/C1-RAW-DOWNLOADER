import json,re,io,os,hashlib
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
def digest(b):return hashlib.sha256(b).hexdigest()
c=Credentials(token=None,refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],client_id=os.environ['GOOGLE_CLIENT_ID'],client_secret=os.environ['GOOGLE_CLIENT_SECRET'],token_uri='https://oauth2.googleapis.com/token',scopes=['https://www.googleapis.com/auth/drive'])
c.refresh(Request())
s=build('drive','v3',credentials=c,cache_discovery=False)
src='1-31-lNq_IL2gxDN8u_upzFmIM3ZznKQe'
original=s.files().get_media(fileId=src).execute()
t=pq.read_table(io.BytesIO(original))
fields=['foreign_independent','foreign_dealer','foreign_combined','trust','dealer_proprietary','dealer_hedge','dealer_combined']
converted=[];bad=0;other=0;dates=set()
for row in t.to_pylist():
 code=str(row.get('security_id') or '')
 if not re.fullmatch(r'[0-9]{4}',code):other+=1;continue
 names=json.loads(row['native_fields_json'])
 if len(names)!=24:bad+=1;continue
 native=json.loads(row['native_row_json'])
 try:values=[int(str(native[f'{i}:{names[i]}']).replace(',','')) for i in range(2,24)]
 except (KeyError,ValueError,TypeError):bad+=1;continue
 groups={name:values[i*3:i*3+3] for i,name in enumerate(fields)}
 if any(a-b!=v for a,b,v in groups.values()):bad+=1;continue
 if groups['foreign_independent'][2]+groups['foreign_dealer'][2]!=groups['foreign_combined'][2]:bad+=1;continue
 if groups['dealer_proprietary'][2]+groups['dealer_hedge'][2]!=groups['dealer_combined'][2]:bad+=1;continue
 if groups['foreign_combined'][2]+groups['trust'][2]+groups['dealer_combined'][2]!=values[21]:bad+=1;continue
 output={'date':row['trade_date'],'stock_id':code,'market':'OTC','institution_total_shares':values[21],'native_sha256':row['source_sha256']}
 for name,(buy,sell,net) in groups.items():
  output[name+'_buy_shares']=buy;output[name+'_sell_shares']=sell;output[name+'_net_shares']=net
 dates.add(row['trade_date']);converted.append(output)
if len(dates)!=20 or len(converted)/max(1,len(converted)+bad)<.98:raise ValueError('INTEGRITY_GATE_FAILED')
buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(converted),buf,compression='zstd')
def save(parent,name,blob):
 p=s.files().create(body={'name':name,'parents':[parent]},media_body=MediaIoBaseUpload(io.BytesIO(blob),mimetype='application/octet-stream'),fields='id').execute()['id']
 if digest(s.files().get_media(fileId=p).execute())!=digest(blob):raise ValueError('SHA_MISMATCH')
 return p
sid=save('1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U','202609_TPEX_INST_SILVER_V2.parquet',buf.getvalue())
gold=[{'date':r['date'],'stock_id':r['stock_id'],'foreign_net_shares':r['foreign_combined_net_shares'],'trust_net_shares':r['trust_net_shares'],'dealer_net_shares':r['dealer_combined_net_shares'],'total_net_shares':r['institution_total_shares'],'historical_pit_verified':False} for r in converted]
b=io.BytesIO();pq.write_table(pa.Table.from_pylist(gold),b,compression='zstd')
gid=save('1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3','202609_TPEX_INST_GOLD_V2.parquet',b.getvalue())
print(json.dumps({'source_rows':t.num_rows,'silver_rows':len(converted),'quality_rejects':bad,'out_of_scope_rows':other,'silver_id':sid,'gold_id':gid,'historical_pit_verified':False},ensure_ascii=False))
