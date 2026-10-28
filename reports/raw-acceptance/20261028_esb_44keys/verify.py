import urllib.request,urllib.parse,json,concurrent.futures,hashlib,pathlib,datetime
P=pathlib.Path(__file__).parent
codes=['1269','1271','1293','1343','1480','1594']
def get(c):
 u='https://www.tpex.org.tw/www/zh-tw/emerging/historical?'+urllib.parse.urlencode(dict(code=c,date='2026/09/01',type='Monthly',response='json'))
 b=urllib.request.urlopen(u,timeout=30).read(); (P/(c+'.json')).write_bytes(b);o=json.loads(b)
 assert o['stat']=='ok';t=o['tables'][0];assert t['title']=='興櫃個股歷史行情'
 return c,dict(url=u,sha256=hashlib.sha256(b).hexdigest(),response=o)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex: data=dict(ex.map(get,codes))
items=json.load(open('round3_evidence/isolated_price_relationships.json'))['items'];result=[]
for x in items:
 c=x['code'];d=x['date'];roc=str(int(d[:4])-1911)+'/'+d[5:7]+'/'+d[8:];rows=data[c]['response']['tables'][0]['data'];matches=[r for r in rows if r[0]==roc];assert len(matches)==1
 r=matches[0];v=x['native_values'];num=lambda s:float(s.replace(',',''))
 checks={k:num(r[i])==float(v[k]) for k,i in [('max',3),('min',4),('Trading_Volume',1),('Trading_money',2)]}
 idx=rows.index(r);prev=num(rows[idx-1][5]) if idx>0 else None
 result.append(dict(code=c,date=d,as_of_market='TPEx_ESB',official_row=r,comparisons=checks,previous_row_average=prev,open_matches_previous_row_average=None if prev is None else prev==v['open'],close_not_verified=True,raw_reference=x['reference'],market_evidence_sha256=data[c]['sha256']))
out=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_manifest={c:{k:v for k,v in d.items() if k!='response'} for c,d in data.items()},rows=result,keys=len(result),as_of_market_evidenced=len(result),four_field_all_match=sum(all(r['comparisons'].values()) for r in result),mismatches=[r for r in result if not all(r['comparisons'].values())],formal_release_approved=False,raw_changed=False,note='ESB retained RAW only policy remains. No official closing-price proof; no blanket acceptance. Previous available row is not certified trading calendar predecessor.')
(P/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['rows','source_manifest','mismatches']},ensure_ascii=False));print('mismatch_keys',[(r['code'],r['date'],r['comparisons']) for r in out['mismatches']])
