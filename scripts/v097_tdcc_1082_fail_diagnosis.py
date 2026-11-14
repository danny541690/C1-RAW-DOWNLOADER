#!/usr/bin/env python3
"""Read frozen immutable per-file strict QA receipts, report actual failure reasons."""
import json,re
from collections import Counter
from scripts.v097_bronze_first_pipeline import service,common,children,load_json,match
api=service();_,c,q,_=common(api)
groups=Counter();examples={}
for f in children(api,q):
 if not re.match(r"^v097_TDCC_1084_INTERNAL_PROOF_RAW_(?:43521294768|43531417736|43532045738)_L\d\d_O\d+(?:_[a-f0-9]{12})?\.json$",f["name"]):continue
 data=load_json(api,f["id"])
 for r in data.get("rows",[]):
  err=r.get("error","?")
  groups[(f["name"].split("_L")[0].split("_")[-1],err)]+=1
  examples.setdefault(str((f["name"].split("_L")[0].split("_")[-1],err)),{"file_id":r.get("file_id"),"date":r.get("date"),"code":r.get("code")})
print("REASONS="+json.dumps({"total":sum(groups.values()),"causes":{str(k):v for k,v in groups.items()},"examples":examples},ensure_ascii=False))

from scripts.v097_bronze_first_pipeline import call
from bs4 import BeautifulSoup
for p in ("1KKTtdvC2pkdwN8GjbJn9eJH7P0VgFi5a","1121GA2OnaetYt4H37BP1dCNZzIBpliB2"):
    raw=call(lambda:api.files().get_media(fileId=p))
    soup=BeautifulSoup(raw.decode("utf-8-sig"),"html.parser")
    tab=next(t for t in soup.select("table") if "持股/單位數分級" in t.get_text(" ",strip=True))
    levels=[]
    for tr in tab.select("tr"):
        cells=[x.get_text(" ",strip=True) for x in tr.find_all("td",recursive=False)]
        if len(cells)==5:
            levels.append([cells[0],cells[1],cells[2],cells[3],cells[4]])
    print("HTML_REAL_LEVELS="+json.dumps({"file":p,"rows":levels[-6:]},ensure_ascii=False))

from decimal import Decimal
for p in ("1KKTtdvC2pkdwN8GjbJn9eJH7P0VgFi5a",):
    raw=call(lambda:api.files().get_media(fileId=p))
    soup=BeautifulSoup(raw.decode("utf-8-sig"),"html.parser")
    tab=next(t for t in soup.select("table") if "持股/單位數分級" in t.get_text(" ",strip=True))
    a=[]
    for tr in tab.select("tr"):
       t=[x.get_text(" ",strip=True).replace(",","") for x in tr.find_all("td",recursive=False)]
       if len(t)==5 and t[0].isdigit():a.append((int(t[0]),int(t[2]),int(t[3]),Decimal(t[4]),t[1]))
    print("TABLE_INVARIANTS="+json.dumps({"rows":len(a),"sum_holders":sum(x[1] for x in a[:-1]),"sum_shares":sum(x[2] for x in a[:-1]),"sum_pct":str(sum(x[3] for x in a[:-1])),"last":str(a[-1])},ensure_ascii=False))
