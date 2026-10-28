import urllib.request,urllib.parse,concurrent.futures,pathlib,json,hashlib
P=pathlib.Path(__file__).parent
codes=['1269','1271','1293','1343','1480','1594']
def get(c):
 u='https://www.tpex.org.tw/www/zh-tw/emerging/historical?'+urllib.parse.urlencode(dict(code=c,date='2026/08/01',type='Monthly',response='json'))
 b=urllib.request.urlopen(u,timeout=35).read();o=json.loads(b);assert o['stat']=='ok';assert o['tables'][0]['title']=='興櫃個股歷史行情';(P/(c+'_202608.json')).write_bytes(b);return c,dict(url=u,sha256=hashlib.sha256(b).hexdigest(),rows=len(o['tables'][0]['data']))
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e: m=dict(e.map(get,codes))
(P/'august_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));print(m)
