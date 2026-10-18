"""Four free-source real mini E2E: one bounded historical sample per source.
Not full market. Do not reuse these samples as annual production coverage.
"""
import hashlib,json,os,time,urllib.request,urllib.parse,http.client,socket
from scripts.annual_actual_firstpass import Drive,service,valid
SAMPLES={
"TWSE":("https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20240102&stockNo=2330&response=json","json"),
"TPEx":("https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?response=json&date=2024%2F01%2F02","json"),
"MOPS":("https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_113_1_0.html","html"),
"FinMind":("https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=2330&start_date=2024-01-01&end_date=2024-01-31","json")}
def fetch(url):
    for n in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=45) as response:
                data=response.read(15000001)
                if len(data)>15000000:raise ValueError("oversize response")
                return data
        except (http.client.IncompleteRead,TimeoutError,socket.timeout,ConnectionError,OSError):
            if n==3:raise
            time.sleep(min(2**n,4))
def run():
    d=Drive(service())
    root=d.folder(d.folder(os.environ["GOOGLE_DRIVE_FOLDER_ID"],"2024"),"_FOUR_SOURCE_MINI_E2E")
    out={}
    for source,(url,kind) in SAMPLES.items():
        folder=d.folder(root,source);filename="2024-01_SAMPLE."+kind
        old=d.read(folder,filename)
        raw=old if old is not None else fetch(url)
        valid(source,raw,kind)
        if old is None:d.put(folder,filename,raw,"application/json" if kind=="json" else "text/html")
        digest=hashlib.sha256(raw).hexdigest()
        receipt={"source":source,"sample_only":True,"sha256":digest,"bytes":len(raw),"numeric_verified":False,"pit_verified":False}
        d.put(folder,filename+".receipt.json",json.dumps(receipt).encode(),"application/json",overwrite=True)
        got=d.read(folder,filename)
        if got is None or hashlib.sha256(got).hexdigest()!=digest:raise ValueError(source+" readback mismatch")
        out[source]={"status":"PASS","bytes":len(raw),"sha256_verified":True,"download_skipped":old is not None}
        print(json.dumps({"source":source,**out[source]}),flush=True)
    print(json.dumps({"result":"FOUR_SOURCE_MINI_PASS","scope":"SAMPLES_ONLY","sources":out}),flush=True)
if __name__=="__main__":run()
