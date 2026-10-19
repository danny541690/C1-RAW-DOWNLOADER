"""Investigate native formats of two pilot months without modifying RAW."""
import argparse,io,json,zipfile,hashlib,re,collections
from scripts.v093_standard_r1 import Drive,service,ROOT,folder,ls
def diagnose(b,n):
 out={"member":n,"bytes":len(b),"signature_hex":b[:12].hex()}
 s=b[:200].decode("utf-8-sig",errors="replace")
 out["prefix"]=repr(s[:140])
 for enc in ("utf-8-sig","cp950"):
  try:
   t=b.decode(enc)
   out["encoding"]=enc
   try:
    o=json.loads(t)
    out["root"]=type(o).__name__
    if isinstance(o,dict):
     out["keys"]=list(o)[:30]
     for k in ("date","Date","stat","status","title","fields","data","tables","aaData"):
      v=o.get(k)
      if isinstance(v,list):
       out[k+"_len"]=len(v)
       if v and isinstance(v[0],dict):
        out[k+"_first_keys"]=list(v[0])[:25]
        if k=="tables":
         out["first_table_fields"]=v[0].get("fields",[])[:20]
         out["first_table_data_first"]=repr(v[0].get("data",[])[:1])[:600]
       elif v:out[k+"_first"]=repr(v[0])[:250]
      elif v is not None:out[k]=repr(v)[:100]
    elif isinstance(o,list):
     out["list_length"]=len(o)
     out["first"]=repr(o[0])[:550] if o else None
   except Exception as e:out["json_error"]=str(e)[:150]
   break
  except UnicodeDecodeError:continue
 return out
def main(yr,mo):
 d=Drive(service());p=f"{yr}-{mo:02d}";root=folder(d,ROOT,str(yr))
 for source in ("TWSE","TPEx","MOPS","FinMind"):
  x=folder(d,folder(d,root,source),p)
  for f in sorted([f for f in ls(d,x) if f["name"].endswith(".zip")],key=lambda x:x["name"]):
   print(json.dumps({"archive":f["name"],"source":source},ensure_ascii=False),flush=True)
   with zipfile.ZipFile(io.BytesIO(d.call(lambda:d.api.files().get_media(fileId=f["id"])))) as z:
    names=[n for n in z.namelist() if n.endswith((".raw",".json",".jsonl",".csv")) and "manifest" not in n and "receipt" not in n]
    sample=names[:5]
    more=next((n for n in names if "prices" in n and n not in sample),None)
    if more:sample.append(more)
    for n in sample:print(json.dumps(diagnose(z.read(n)[:5000000],n),ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True);p.add_argument("--month",type=int,required=True);a=p.parse_args();main(a.year,a.month)
