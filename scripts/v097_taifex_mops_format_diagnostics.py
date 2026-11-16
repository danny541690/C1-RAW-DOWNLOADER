#!/usr/bin/env python3
"""JARVIS v0.97 focused native failure diagnostics, zero release privileges.
TAIFEX CSV: inspect width anomalies while preserving exact original logical rows.
MOPS ZIP: fingerprint member payload by bytes and enumerate matrix/raw types.
"""
import io,csv,json,re,sys,zipfile
from collections import Counter
from scripts.v097_b_format_forensics import fingerprint,safe_name
from scripts.v097_bronze_autopilot import digest
MAX_ROWS=100000
MAX_MEMBERS=400
MAX_UNPACKED=100*1024*1024
MAX_MEMBER=20*1024*1024
def taifex_csv_width_diagnostic(blob):
 text=None;codec=None
 for c in ("utf-8-sig","cp950","big5"):
  try:text=blob.decode(c);codec=c;break
  except UnicodeError:pass
 if text is None:return {"status":"HOLD_TAIFEX_ENCODING","release":False}
 lines=[s for s in text.splitlines() if s.strip()]
 if len(lines)<2:return {"status":"HOLD_TAIFEX_NO_DATA","release":False}
 delimiter=next((d for d in (",","\t",";") if lines[0].count(d)>=2),",")
 try:
  parsed=csv.reader(io.StringIO(text),delimiter=delimiter)
  head=next(parsed,[])
  widths=Counter();footer=0;repeat_headers=0;singletons=[];count=0
  whitespace_only_extra=0;nonempty_extra=0;short_rows=0
  for row in parsed:
   if not any(x.strip() for x in row):continue
   count+=1
   if count>MAX_ROWS:return {"status":"HOLD_TAIFEX_ROW_LIMIT","release":False}
   widths[len(row)]+=1
   if len(row)>len(head):
    if any(str(x).strip() for x in row[len(head):]):nonempty_extra+=1
    else:whitespace_only_extra+=1
   elif len(row)<len(head):short_rows+=1
   if len(row)==1:
    footer+=1
    if len(singletons)<4:singletons.append(str(row[0])[:80])
   if [x.strip() for x in row]==[x.strip() for x in head]:repeat_headers+=1
  expected=len(head)
  anomalies={str(n):v for n,v in widths.items() if n!=expected}
  trailing_empty=widths.get(expected+1,0)
  reason="HOLD_TAIFEX_MIXED_LAYOUT_REQUIRES_VERSIONED_SCHEMA"
  if anomalies and set(anomalies)=={str(expected+1)}:
   reason=("CANDIDATE_TAIFEX_TRAILING_EMPTY_COLUMN_DETECTED_NO_DATA_LOSS"
      if whitespace_only_extra==trailing_empty and nonempty_extra==0
      else "HOLD_TAIFEX_NONEMPTY_EXTRA_COLUMN")
  if nonempty_extra or short_rows:reason="HOLD_TAIFEX_MIXED_LAYOUT_REQUIRES_VERSIONED_SCHEMA"
  if not anomalies:reason="CANDIDATE_VALID_CSV_WIDTH_REQUIRE_DATE_AND_SOURCE_QA"
  return {"status":reason,"encoding":codec,"delimiter":repr(delimiter),
    "header_width":expected,"header_tokens":[str(x)[:45] for x in head[:24]],
    "row_count":count,"row_width_histogram":dict(widths),
    "anomaly_widths":anomalies,"repeated_headers":repeat_headers,
    "singleton_lines":footer,"singleton_samples":singletons,
    "trailing_column_candidates":trailing_empty,
    "whitespace_only_extra_rows":whitespace_only_extra,
    "nonempty_extra_rows":nonempty_extra,"short_rows":short_rows,
    "candidate_normalization_reversible":bool(whitespace_only_extra and not nonempty_extra and not short_rows),
    "original_bytes_preserved":True,"release":False}
 except (csv.Error,UnicodeError) as e:
  return {"status":"HOLD_TAIFEX_CSV_READER_ERROR","error_type":type(e).__name__,"release":False}
def mops_zip_member_diagnostic(blob):
 if not zipfile.is_zipfile(io.BytesIO(blob)):return {"status":"HOLD_MOPS_NOT_ZIP","release":False}
 hist=Counter();dataset=Counter();samples=[];unpacked=0
 try:
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   members=z.infolist()
   if len(members)>MAX_MEMBERS:return {"status":"HOLD_MOPS_ARCHIVE_MEMBER_LIMIT","release":False}
   for m in members:
    if m.is_dir():continue
    if not safe_name(m.filename) or m.file_size>MAX_MEMBER:
     return {"status":"HOLD_MOPS_UNSAFE_OR_LARGE_MEMBER","release":False}
    unpacked+=m.file_size
    if unpacked>MAX_UNPACKED:return {"status":"HOLD_MOPS_EXPANSION_LIMIT","release":False}
    raw=z.read(m)
    f=fingerprint(m.filename,raw)
    hist[f["signature"]]+=1
    dataset[f["dataset_fingerprint"]]+=1
    if len(samples)<15:
     samples.append({"member":m.filename[:110],"signature":f["signature"],
       "dataset_fingerprint":f["dataset_fingerprint"],"sha256":digest(raw),
       "fields":f.get("field_names",[])[:8],"keys":f.get("key_names",[])[:8]})
  return {"status":"MOPS_ARCHIVE_CONTENT_FINGERPRINTED_FINANCIAL_PIT_PENDING",
    "member_count":sum(hist.values()),"format_histogram":dict(hist),
    "dataset_fingerprints":dict(dataset),"samples":samples,
    "original_published_figures_independently_checked":False,
    "accounting_period_and_revision_verified":False,"release":False}
 except (zipfile.BadZipFile,RuntimeError,ValueError,UnicodeError) as e:
  return {"status":"HOLD_MOPS_ARCHIVE_DECODE_ERROR","error_type":type(e).__name__,"release":False}
def selftest():
 a=b"\xef\xbb\xbf"+("交易日期,商品代號,成交口數\n20261113,TX,123,\n20261112,TX,456,\n").encode()
 x=taifex_csv_width_diagnostic(a)
 assert x["header_width"]==3 and x["trailing_column_candidates"]==2 and not x["release"]
 assert x["whitespace_only_extra_rows"]==2 and x["candidate_normalization_reversible"]
 not_empty=taifex_csv_width_diagnostic(b"A,B,C\\n1,2,3,4\\n".replace(b"\\n",b"\n"))
 assert not_empty["nonempty_extra_rows"]==1 and not not_empty["candidate_normalization_reversible"]
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:
  z.writestr("statement.raw",json.dumps({"fields":["公司代號","營業收入"],"data":[["2330","100"]]},ensure_ascii=False).encode())
  z.writestr("manifest.json",b'{"units":[]}')
 m=mops_zip_member_diagnostic(b.getvalue())
 assert m["format_histogram"]["JSON"]==2 and m["release"] is False
 assert m["samples"][0]["signature"]=="JSON"
 print("TAIFEX_MOPS_TYPED_DIAGNOSTIC_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 else:raise SystemExit("usage: selftest")
