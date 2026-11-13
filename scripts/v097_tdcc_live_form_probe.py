#!/usr/bin/env python3
"""Inspect current official TDCC portal query form to find verified endpoint/fields.
No raw extraction beyond non-sensitive form names and date dropdowns.
"""
import os,re,json,requests
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
URL="https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
def run():
    s=requests.Session()
    r=s.get(URL,timeout=(10,25),headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    soup=BeautifulSoup(r.content,"html.parser")
    forms=[]
    for form in soup.select("form"):
        fields=[]
        for inp in form.select("input,select"):
            name=inp.get("name") or inp.get("id") or ""
            if not name:continue
            vals=[]
            if inp.name=="select":
                vals=[{"value":a.get("value"),"label":a.get_text(" ",strip=True)} for a in inp.select("option")[:12]]
            fields.append({"name":name,"kind":inp.name,"type":inp.get("type"),"values":vals,
                           "hidden_present":inp.get("type")=="hidden"})
        forms.append({"action":form.get("action"),"method":form.get("method"),"id":form.get("id"),"fields":fields[:35]})
    scripts=[]
    for js in soup.select("script"):
        code=js.get_text(" ",strip=True)
        for term in ["scaDate","stockNo","sqlMethod","qryStock","submit"]:
            i=code.find(term)
            if i>=0:scripts.append({"keyword":term,"around":code[max(0,i-130):i+180]})
    obs={"url":URL,"http":r.status_code,"forms":forms[:6],"script_hints":scripts[:15],
         "date_options":list(dict.fromkeys([o.get("value") for f in forms for item in f["fields"] for o in item.get("values",[]) if re.fullmatch(r"20\d{6}",str(o.get("value") or ""))]))[:12]}
    api=service();_,_,q,_=common(api)
    put_once(api,q,"v097_TDCC_LIVE_FORM_%s.json"%RUN,obs)
    print("TDCC_LIVE_FORM="+json.dumps(obs,ensure_ascii=False),flush=True)
if __name__=="__main__":run()
