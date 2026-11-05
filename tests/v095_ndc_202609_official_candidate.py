"""Fetch genuine NDC 11509 published XLSX via official 2026-10-29 news item.

This is a bounded candidate recovery, not a full macro-universe release.
Requires the attachment link to be associated with 11509 data-series label.
"""
import hashlib,io,json,pathlib,urllib.parse,zipfile,requests
from bs4 import BeautifulSoup
OUT=pathlib.Path("v095_ndc_202609_official_candidate")
OUT.mkdir(exist_ok=True)
PAGE="https://www.ndc.gov.tw/nc_332_40618"
ALLOW={"www.ndc.gov.tw","ws.ndc.gov.tw"}
def get(url,size):
  r=requests.get(url,timeout=35,headers={"User-Agent":"Mozilla/5.0 (JARVIS-v095-Bronze-official-pilot)","Accept-Encoding":"identity"},stream=True)
  r.raise_for_status()
  result=b""
  for part in r.iter_content(chunk_size=256*1024):
    result+=part
    if len(result)>size:raise ValueError("SOURCE_SIZE_CAP")
  if urllib.parse.urlsplit(r.url).hostname not in ALLOW:raise ValueError("REDIRECT_HOST_NOT_OFFICIAL")
  return result,r.url
def main():
 report={"schema":"JARVIS_V095_NDC_11509_SOURCE_CANDIDATE","period":"2026-09",
         "source":"NDC","source_publication_date":"2026-10-29","production_approved":False,
         "status":"BLOCKED"}
 try:
  html,final=get(PAGE,3*1024*1024)
  soup=BeautifulSoup(html,"html.parser")
  candidates=[]
  for text in soup.find_all(string=lambda x:bool(x and "11509新聞稿附件數列" in str(x))):
    parent=text.parent
    for _ in range(5):
      if parent is None:break
      for a in parent.find_all("a",href=True):
       h=a["href"];label=a.get_text(" ",strip=True)
       if "xlsx" in (h+" "+label).lower():
        url=urllib.parse.urljoin(PAGE,h)
        if urllib.parse.urlsplit(url).hostname in ALLOW:
         candidates.append(url)
      if candidates:break
      parent=parent.parent
  candidates=list(dict.fromkeys(candidates))
  if len(candidates)!=1:raise ValueError("EXPECTED_ONE_11509_XLSX_ATTACHMENT_FOUND_"+str(len(candidates)))
  raw,actual=get(candidates[0],12*1024*1024)
  if not raw.startswith(bytes([80,75,3,4])):raise ValueError("NOT_XLSX_ZIP")
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if "[Content_Types].xml" not in z.namelist() or "xl/workbook.xml" not in z.namelist():raise ValueError("NOT_OOXML_WORKBOOK")
    if z.testzip() is not None:raise ValueError("ZIP_CRC")
  p=OUT/"NDC_11509_official_series.xlsx"
  p.write_bytes(raw)
  if hashlib.sha256(p.read_bytes()).hexdigest()!=hashlib.sha256(raw).hexdigest():raise ValueError("RAW_READBACK")
  report.update(status="OFFICIAL_NDC_XLSX_CAPTURED_CANDIDATE",attachment_url=actual,
                source_page=PAGE,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                full_month_universe_verified=False,pit_timestamp="2026-10-29")
 except Exception as e:
  report["error"]=type(e).__name__+":"+str(e)[:500]
 (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report["status"]=="BLOCKED":raise SystemExit(1)
if __name__=="__main__":main()
