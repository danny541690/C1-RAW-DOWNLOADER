#!/usr/bin/env python3
"""JARVIS v0.97 R2 - read-only historical content audit.
Fixed 12 shards, immutable per-batch receipts, independent lane checkpoints.
Parsed/structural success is NOT PIT or financial numeric certification.
"""
import csv,hashlib,io,json,os,re,zipfile,math
from collections import Counter
from html.parser import HTMLParser
from datetime import datetime,timezone
from scripts.v097_bronze_content_qa import service,call,children,folder,load_json,save
from scripts.v097_bronze_diagnosis import save_or_update
SOURCE_RUN="42591232910"
SPLITS={"TWSE":(0,1),"TPEx":(2,3),"TDCC":(4,5,6,7),"TDCC_ARCHIVE":(4,5,6,7),"TAIFEX":(8,9),"MOPS":(10,),"NDC":(11,),"FinMind":(11,)}
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=min(120,max(1,int(os.getenv("R2_BATCH","80"))))
CYCLES=min(40,max(1,int(os.getenv("R2_CYCLES","12"))))
def utc():return datetime.now(timezone.utc).isoformat()
def dirs(api):
    u=folder(api,"root","ChatGPT資料存取");v=folder(api,u,"JARVIS_C1_v097_LIFECYCLE")
    c=folder(api,v,"00_SYSTEM_CONTROL");q=folder(api,v,"03_DATA_QUALITY")
    return folder(api,c,"03_RUN_MANIFESTS"),folder(api,c,"04_CHECKPOINTS"),folder(api,q,"07_VERIFICATION_REPORTS")
def one(api,parent,name):
    a=[x for x in children(api,parent) if x["name"]==name]
    if len(a)>1:raise RuntimeError("Duplicate file "+name)
    return a[0] if a else None
def lane_id(row):
    options=SPLITS.get(row.get("source"))
    if not options:raise RuntimeError("Unexpected source: "+str(row.get("source")))
    return options[int(hashlib.sha256(row["file_id"].encode()).hexdigest(),16)%len(options)]
def prepare(api):
    m,_,_=dirs(api);marker=one(api,m,"v097_R2_FROZEN.json")
    if marker:
        d=load_json(api,marker["id"])
        if d.get("source_run")!=SOURCE_RUN or d.get("eligible")!=82273:raise RuntimeError("Frozen inventory conflict")
        for k in range(12):
            if not one(api,m,"v097_R2_MANIFEST_%02d.json"%k):raise RuntimeError("Missing frozen lane manifest")
        print("R2_ALREADY_PREPARED",flush=True);return
    shards={i:[] for i in range(12)};seen=set();excluded=0
    for i in range(6):
        filename="v097_inventory_%s_lane%d.json"%(SOURCE_RUN,i)
        f=one(api,m,filename)
        if not f:raise RuntimeError("Missing first-pass inventory "+filename)
        d=load_json(api,f["id"])
        if d.get("run_id")!=SOURCE_RUN or d.get("lane")!=i or d.get("errors"):raise RuntimeError("Bad prior inventory")
        for r in d["files"]:
            fid=r["file_id"]
            if fid in seen:raise RuntimeError("Duplicate source file id")
            seen.add(fid)
            if r.get("classification")=="TEST_OR_CONTROL":excluded+=1;continue
            shards[lane_id(r)].append({k:r.get(k) for k in ("file_id","file_name","source","year","month","path","size_bytes","md5","classification")})
    if len(seen)!=83249 or excluded!=976 or sum(map(len,shards.values()))!=82273:raise RuntimeError("Frozen inventory count mismatch")
    for k,rows in shards.items():
        name="v097_R2_MANIFEST_%02d.json"%k
        v={"schema":"r2_manifest_1","lane":k,"files":sorted(rows,key=lambda r:r["file_id"])}
        prior=one(api,m,name)
        if prior:
            if load_json(api,prior["id"])!=v:raise RuntimeError("Partial bootstrap checksum conflict")
        else:save(api,m,name,v)
        print("R2_SHARD",k,len(rows),flush=True)
    save(api,m,"v097_R2_FROZEN.json",{"schema":"r2_frozen_1","source_run":SOURCE_RUN,"eligible":82273,"excluded":976,"created_at":utc(),"counts":{str(k):len(v) for k,v in shards.items()},"certified":False})
    print("R2_FROZEN_COMPLETE",flush=True)
class HTMLCount(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=0;self.rows=0;self.cells=0
    def handle_starttag(self,t,a):
        if t=="table":self.tables+=1
        if t=="tr":self.rows+=1
        if t in ("td","th"):self.cells+=1
def decode(data):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try:return data.decode(enc),enc
        except UnicodeDecodeError:pass
    raise ValueError("Cannot decode source text")
def inspect(r,data):
    name=r["file_name"];ext=name.lower().rsplit(".",1)[-1] if "." in name else ""
    v={"file_id":r["file_id"],"source":r["source"],"year":r["year"],"path":r["path"],"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"pit":"PIT_UNVERIFIED","status":"UNRESOLVED","timestamp":utc()}
    if not data:v["status"]="QUARANTINED_EMPTY";return v
    if r.get("md5") and hashlib.md5(data).hexdigest()!=r["md5"]:
        v["status"]="QUARANTINED_MD5_MISMATCH";return v
    if r.get("size_bytes") and len(data)!=int(r["size_bytes"]):
        v["status"]="QUARANTINED_SIZE_MISMATCH";return v
    if ext=="zip" or data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                inf=z.infolist();v["members"]=len(inf);size=sum(x.file_size for x in inf)
                v["uncompressed_bytes"]=size
                if not inf:v["status"]="QUARANTINED_EMPTY_ZIP";return v
                if any(x.filename.startswith("/") or ".." in x.filename.split("/") for x in inf):
                    v["status"]="QUARANTINED_UNSAFE_ZIP";return v
                if size>192*1024*1024:v["status"]="EXCEPTION_NEEDS_STREAMED_ZIP_PARSER";return v
                for x in inf:
                    if x.is_dir():continue
                    with z.open(x) as f:
                        while f.read(262144):pass
                controls=sum(bool(re.search("manifest|checkpoint|receipt|report|control",x.filename,re.I)) for x in inf)
                v["control_members"]=controls
                v["status"]="ZIP_MIXED_ARCHIVE_CONTENT_PENDING" if controls else "ZIP_CRC_PASS_CONTENT_PENDING"
                return v
        except (zipfile.BadZipFile,RuntimeError,OSError,EOFError,ValueError) as ex:
            v["status"]="QUARANTINED_ZIP_ERROR";v["error"]=type(ex).__name__;return v
    if ext in ("json","raw") or data[:1024].lstrip().startswith((b"{",b"[")):
        try:
            obj=json.loads(data.decode("utf-8-sig"))
            if isinstance(obj,dict):
                v["top_keys"]=list(obj)[:30]
                arrays=[(k,x) for k,x in obj.items() if isinstance(x,list) and x and isinstance(x[0],(dict,list))]
                v["dataset_arrays"]={k:len(x) for k,x in arrays[:25]}
                if not arrays:v["status"]="JSON_SCHEMA_CONTENT_PENDING";return v
                sample=sum(len(a[:100]) for _,a in arrays[:12])
                v["sample_records"]=sample
                v["status"]="JSON_ROWS_PARSED_PIT_PENDING" if sample else "JSON_SCHEMA_CONTENT_PENDING"
            elif isinstance(obj,list):
                v["record_count"]=len(obj)
                v["status"]="JSON_ROWS_PARSED_PIT_PENDING" if obj else "QUARANTINED_EMPTY_JSON"
            else:v["status"]="JSON_SCHEMA_CONTENT_PENDING"
            return v
        except (UnicodeError,ValueError,TypeError) as ex:
            v["status"]="QUARANTINED_JSON_ERROR";v["error"]=type(ex).__name__;return v
    if ext in ("html","htm") or b"<html" in data[:2048].lower():
        try:
            t,_=decode(data);p=HTMLCount();p.feed(t)
            v.update(tables=p.tables,table_rows=p.rows,table_cells=p.cells)
            v["status"]="TDCC_TABLE_NUMERIC_PENDING" if r["source"]=="TDCC" and p.tables and p.rows>=4 and p.cells>=8 else "HTML_TABLE_CONTENT_PENDING" if p.tables and p.cells else "HTML_SCHEMA_PENDING"
            return v
        except ValueError:v["status"]="QUARANTINED_HTML_DECODING";return v
    if ext in ("csv","txt","tsv"):
        try:
            t,_=decode(data)
            rows=list(csv.reader(io.StringIO(t[:1000000]),delimiter="\t" if ext=="tsv" else ","))[:100]
            v["sample_widths"]=dict(Counter(len(x) for x in rows))
            v["status"]="CSV_SCHEMA_CONTENT_PENDING" if rows and max(map(len,rows))>1 else "CSV_SCHEMA_PENDING"
            return v
        except (ValueError,csv.Error):v["status"]="QUARANTINED_TEXT_PARSE";return v
    if ext=="pdf":
        v["status"]="PDF_CONTENT_PENDING" if data.startswith(b"%PDF") and b"%%EOF" in data[-2048:] else "QUARANTINED_PDF_INVALID";return v
    if ext in ("xls","xlsx"):v["status"]="EXCEPTION_SPREADSHEET_PARSER_PENDING";return v
    v["status"]="EXCEPTION_UNKNOWN_FORMAT";return v
def worker(api,k):
    m,c,q=dirs(api);f=one(api,m,"v097_R2_MANIFEST_%02d.json"%k)
    if not f:raise RuntimeError("Missing R2 frozen manifest")
    rows=load_json(api,f["id"])["files"]
    cname="v097_R2_CK_%02d.json"%k;fck=one(api,c,cname)
    state=load_json(api,fck["id"]) if fck else {"schema":"r2_ck_1","lane":k,"done":[],"counts":{}}
    if state["schema"]!="r2_ck_1" or state["lane"]!=k:raise RuntimeError("Checkpoint mismatch")
    done=set(state["done"]);allowed={r["file_id"] for r in rows}
    if not done.issubset(allowed):raise RuntimeError("Cross-lane checkpoint corruption")
    counts=Counter(state["counts"])
    for cycle in range(CYCLES):
        todo=[r for r in rows if r["file_id"] not in done][:BATCH]
        if not todo:break
        recname="v097_R2_%s_%02d_%02d.json"%(RUN,k,cycle)
        receipt=one(api,q,recname)
        if receipt:
            result=load_json(api,receipt["id"])["results"]
            if [x["file_id"] for x in result]!=[x["file_id"] for x in todo]:raise RuntimeError("Receipt/work-order mismatch")
        else:
            result=[]
            for r in todo:
                if int(r.get("size_bytes") or 0)>36*1024*1024:
                    o={"file_id":r["file_id"],"source":r["source"],"status":"EXCEPTION_BOUNDED_SIZE","pit":"PIT_UNVERIFIED"}
                else:
                    try:o=inspect(r,call(lambda:api.files().get_media(fileId=r["file_id"])))
                    except Exception as e:o={"file_id":r["file_id"],"source":r["source"],"status":"EXCEPTION_READ_FAILURE","error":type(e).__name__,"pit":"PIT_UNVERIFIED"}
                result.append(o)
            save(api,q,recname,{"schema":"r2_receipt_1","run_id":RUN,"lane":k,"cycle":cycle,"results":result,"created":utc()})
        for r in result:
            if r["file_id"] not in done:done.add(r["file_id"]);counts[r["status"]]+=1
        state={"schema":"r2_ck_1","lane":k,"done":sorted(done),"counts":dict(counts),"remaining":len(rows)-len(done),"eligible":len(rows),"updated":utc(),"last_run":RUN}
        save_or_update(api,c,cname,state,fck["id"] if fck else None)
        if not fck:fck=one(api,c,cname)
        print("R2_LANE_PROGRESS",k,len(done),len(rows),flush=True)
def aggregate(api):
    m,c,q=dirs(api);freeze=one(api,m,"v097_R2_FROZEN.json")
    base=load_json(api,freeze["id"]);done=0;pending=0;counts=Counter();lanes=[]
    for k in range(12):
        f=one(api,c,"v097_R2_CK_%02d.json"%k)
        if not f:raise RuntimeError("Missing R2 lane checkpoint")
        v=load_json(api,f["id"])
        if v["eligible"]!=base["counts"][str(k)] or len(v["done"])+v["remaining"]!=v["eligible"] or sum(v["counts"].values())!=len(v["done"]):
            raise RuntimeError("R2 checkpoint conservation violation")
        done+=len(v["done"]);pending+=v["remaining"];counts.update(v["counts"])
        lanes.append({"lane":k,"done":len(v["done"]),"remaining":v["remaining"]})
    if done+pending!=base["eligible"]:raise RuntimeError("R2 global count mismatch")
    summary={"schema":"r2_coverage_1","run_id":RUN,"timestamp":utc(),"total":base["eligible"],"processed":done,"remaining":pending,
             "status_counts":dict(counts),"lanes":lanes,"bronze_certified":0,"numeric_certified":0,"pit_certified":0,
             "status":"INITIAL_CONTENT_AUDIT_COMPLETED_REVIEW_PENDING" if pending==0 else "AUTOCONTINUE",
             "note":"First-round semantic pending files are audited. Format and sample checks are NOT financial-content certification."}
    save(api,q,"v097_R2_%s_SUMMARY.json"%RUN,summary)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write("remaining=%d\n"%pending)
    print("R2_AGGREGATE",json.dumps({k:v for k,v in summary.items() if k!="lanes"},ensure_ascii=False),flush=True)
if __name__=="__main__":
    api=service();mode=os.environ["R2_MODE"]
    if mode=="prepare":prepare(api)
    elif mode=="worker":worker(api,int(os.environ["R2_LANE"]))
    elif mode=="aggregate":aggregate(api)
    else:raise RuntimeError("Unknown R2_MODE")
