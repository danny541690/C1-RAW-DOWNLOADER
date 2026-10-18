"""Real bulk market one-day Drive upload and cross-job verification. Not annual coverage."""
import hashlib,json,os,time,urllib.request,http.client,socket
from scripts.annual_actual_firstpass import Drive,service
from scripts.bulk_market_canary import URLS,measure
def fetch(url):
    for n in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=40) as r:return r.read(15000000)
        except (http.client.IncompleteRead,TimeoutError,socket.timeout,ConnectionError,OSError):
            if n==3:raise
            time.sleep(min(2**n,4))
def run():
    d=Drive(service());root=os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    parent=d.folder(d.folder(root,"2024"),"_BULK_INTEGRATION_CANARY")
    mode=os.environ["MODE"]
    summary={}
    for source,url in URLS.items():
        folder=d.folder(parent,source)
        name="2024-01-02.json"
        if mode=="write":
            before=d.read(folder,name)
            if before:
                raw=before
            else:
                raw=fetch(url)
                measure(source,raw)
                d.put(folder,name,raw,"application/json")
            measurement=measure(source,raw)
            checksum=hashlib.sha256(raw).hexdigest()
            d.put(folder,name+".receipt.json",json.dumps({"sha256":checksum,"bytes":len(raw),"scope":"SINGLE_DAY_BULK_ONLY","measurement":measurement}).encode(),"application/json",overwrite=True)
            summary[source]={"rows":measurement["rows"],"bytes":len(raw),"saved":True}
        elif mode=="resume":
            raw=d.read(folder,name)
            receipt_raw=d.read(folder,name+".receipt.json")
            if raw is None or receipt_raw is None:raise ValueError("missing remote bulk canary or receipt")
            receipt=json.loads(receipt_raw)
            if hashlib.sha256(raw).hexdigest()!=receipt["sha256"] or len(raw)!=receipt["bytes"]:raise ValueError("bulk readback mismatch")
            measurement=measure(source,raw)
            summary[source]={"rows":measurement["rows"],"bytes":len(raw),"refetch_count":0,"sha256_verified":True}
        else:raise ValueError("invalid MODE")
    print(json.dumps({"mode":mode,"result":"PASS","scope":"2024-01-02_SINGLE_DAY_ONLY","sources":summary}))
if __name__=="__main__":run()
