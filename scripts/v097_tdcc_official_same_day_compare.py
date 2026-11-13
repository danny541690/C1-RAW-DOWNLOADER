#!/usr/bin/env python3
"""Direct same-code, same-date official live TDCC portal query comparison.
Strictly verify code, selected date, holders/shares; reject HTML landing page
as match. Original source file untouched. Purpose: provenance crosscheck only.
"""
import os,json,re,hashlib,requests
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,put_once
from scripts.v097_tdcc_a3_a5_auto import html_identity,table_diagnostics
RUN=os.getenv("GITHUB_RUN_ID","manual")
URL="https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
CASES=[
 {"date":"20260918","code":"YY0064","old_holders":5241,"old_shares":97670909,"orig_sha":"0ac4b66a1237b6f53f9c3cc92274b68d9ed43b0c06911280f608630c0e330aec"},
 {"date":"20261002","code":"YFJ1","old_holders":1,"old_shares":21000000,"orig_sha":"21634c772be5f6e898546e443d5706d14bed5882264a86def73a5fd93986c14d"},
 {"date":"20261016","code":"YMM2","old_holders":1,"old_shares":2400000,"orig_sha":"fc45525380015131f205a4d44271ef39ab56a9366b2a0e32b7b29b66a65bd6a1"},
 {"date":"20261016","code":"2330","control_only":True}
]
def read_inputs(html):
    soup=BeautifulSoup(html,"html.parser")
    form=soup.select_one("form#form1")
    if not form:raise ValueError("OFFICIAL_FORM_MISSING")
    fields={}
    for elm in form.select("input[type=hidden]"):
        key=elm.get("name")
        if key:fields[key]=elm.get("value","")
    options={x.get("value") for x in form.select("select[name=scaDate] option")}
    radio=form.select("input[name=sqlMethod]")
    methods=[x.get("value") for x in radio]
    return fields,options,methods
def query(session,case):
    res={"code":case["code"],"date":case["date"],"control_only":case.get("control_only",False),
         "old_holders":case.get("old_holders"),"old_shares":case.get("old_shares"),
         "old_original_sha":case.get("orig_sha")}
    try:
        entry=session.get(URL,timeout=(10,25),headers={"User-Agent":"Mozilla/5.0"})
        entry.raise_for_status()
        fields,options,methods=read_inputs(entry.content)
        res["date_in_official_dropdown"]=case["date"] in options
        res["official_available_method_options"]=methods
        if case["date"] not in options:
            res["state"]="DATE_NOT_CURRENTLY_IN_OFFICIAL_QUERY_DROPDOWN";return res
        if "StockNo" not in methods:
            res["state"]="OFFICIAL_FORM_STOCK_QUERY_METHOD_CHANGED";return res
        payload={**fields,"scaDate":case["date"],"sqlMethod":"StockNo",
                 "stockNo":case["code"],"stockName":""}
        resp=session.post(URL,data=payload,timeout=(10,30),
                 headers={"User-Agent":"Mozilla/5.0","Referer":URL})
        res.update(http=resp.status_code,response_bytes=len(resp.content),
                   response_sha256=hashlib.sha256(resp.content).hexdigest(),
                   final_url=resp.url)
        if resp.status_code!=200 or not resp.content:
            res["state"]="OFFICIAL_RESPONSE_NOT_READABLE";return res
        doc=resp.content
        displayed_code,dates,has_table=html_identity(doc)
        # Also support response forms where StockNo ID has been lowercased.
        if not displayed_code:
            s=BeautifulSoup(doc,"html.parser")
            v=s.select_one("input#StockNo, input#stockNo")
            displayed_code=(v.get("value") or "").strip().upper() if v else None
        dist=table_diagnostics(doc)
        res.update(official_content_code=displayed_code,
            official_date_selected=case["date"] in dates,
            official_distribution=dist)
        correct_identity=displayed_code==case["code"] and case["date"] in dates
        if not correct_identity:
            # Some current portal HTML omits selected attr, so do not certify from an arbitrary page.
            res["state"]="OFFICIAL_RESPONSE_CODE_DATE_NOT_PROVED";return res
        if dist.get("status")!="HTML_DISTRIBUTION_TOTALS_MATCH":
            res["state"]="OFFICIAL_RESPONSE_HOLDING_TABLE_NOT_VERIFIED";return res
        res["same_code_date_proved"]=True
        if case.get("control_only"):
            res["state"]="OFFICIAL_STOCK_CONTROL_QUERY_OK";return res
        res["holder_difference"]=dist["total_holders"]-case["old_holders"]
        res["share_difference"]=dist["total_shares"]-case["old_shares"]
        res["state"]="EXACT_SAME_DATE_CONTENT_MATCH" if res["holder_difference"]==res["share_difference"]==0 else "OFFICIAL_HISTORICAL_CONTENT_DIFFERENCE"
    except Exception as ex:res.update(state="OFFICIAL_QUERY_ERROR",error=type(ex).__name__+":"+str(ex)[:170])
    return res
def run():
    session=requests.Session()
    cases=[query(session,r) for r in CASES]
    report={"schema":"v097_tdcc_official_same_date_comparison_1","run":RUN,
        "official_url":URL,"cases":cases,
        "same_date_matches":sum(x["state"]=="EXACT_SAME_DATE_CONTENT_MATCH" for x in cases),
        "unverified":sum(x["state"] not in ("EXACT_SAME_DATE_CONTENT_MATCH","OFFICIAL_STOCK_CONTROL_QUERY_OK") for x in cases),
        "market_membership_certified":False,"originals_unchanged":True}
    api=service();_,_,q,_=common(api)
    put_once(api,q,"v097_TDCC_SAME_DATE_COMPARE_%s.json"%RUN,report)
    print("TDCC_SAME_DATE_COMPARE="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":run()
