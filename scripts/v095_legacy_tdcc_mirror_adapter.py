#!/usr/bin/env python3
"""Strict TDCC source-data schema and mirror-archive receipt adapter.

A preserved v0.93 snapshot from wirelessr/tdcc-opendata-archive is a THIRD-PARTY
mirror, NOT original official TDCC provenance. Never mark PIT/official validated
or feed candidate numeric values into production factor Gold.
"""
import csv,datetime as dt,decimal,hashlib,io,json,pathlib,re,zipfile
D=decimal.Decimal
HEADER=["資料日期","證券代號","持股分級","人數","股數","占集保庫存數比例%"]
def sha(b):return hashlib.sha256(b).hexdigest()
def records(raw,month,source_archive_sha=None,source_file=None):
 if len(raw)>20_000_000:raise ValueError("TDCC_CSV_SIZE_LIMIT")
 try:text=raw.decode("utf-8-sig")
 except UnicodeError:raise ValueError("TDCC_CSV_ENCODING")
 reader=csv.reader(io.StringIO(text))
 if next(reader,None)!=HEADER:raise ValueError("TDCC_CSV_NATIVE_HEADER_MISMATCH")
 out=[];seen=set()
 for row in reader:
  if not any(x.strip() for x in row):continue
  if len(row)!=6:raise ValueError("TDCC_CSV_ROW_WIDTH")
  stamp,code,tier,people,shares,ratio=(x.strip() for x in row)
  if not re.fullmatch(r"20\d{6}",stamp) or stamp[:6]!=month.replace("-",""):
   raise ValueError("TDCC_CSV_DATE_OUTSIDE_REQUEST_MONTH")
  dt.datetime.strptime(stamp,"%Y%m%d")
  if not re.fullmatch(r"\d{4,8}",code) or not re.fullmatch(r"\d{1,2}",tier):
   raise ValueError("TDCC_CSV_SECURITY_TIER_BAD")
  key=(stamp,code,tier)
  if key in seen:raise ValueError("TDCC_CSV_DUPLICATE_STOCK_TIER_DAY")
  seen.add(key)
  if not people.isdigit() or not shares.isdigit():raise ValueError("TDCC_CSV_NONINTEGER_SHARES_OR_PEOPLE")
  try:percent=D(ratio)
  except decimal.InvalidOperation:raise ValueError("TDCC_CSV_PERCENT_INVALID")
  if not percent.is_finite() or not D("0")<=percent<=D("100"):
   raise ValueError("TDCC_CSV_PERCENT_RANGE")
  out.append({"source":"TDCC","original_origin":"THIRD_PARTY_ARCHIVE_NOT_OFFICIAL",
   "snapshot_date":f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}",
   "stock_id":code,"holding_tier":tier,"people_count":int(people),
   "shares":int(shares),"share_percent":percent,
   "source_zip_sha256":source_archive_sha,"source_member":source_file,
   "published_at":None,"pit_verified":False,"official_source_verified":False})
 if not out:raise ValueError("TDCC_CSV_EMPTY")
 return out
def validate_capture_zip(z,month):
 names=z.namelist()
 if names.count("capture_receipts.json")!=1:raise ValueError("TDCC_CAPTURE_RECEIPT_MISSING")
 receipts=json.loads(z.read("capture_receipts.json"))
 if not isinstance(receipts,list) or not 1<=len(receipts)<=64:raise ValueError("TDCC_CAPTURE_RECEIPT_LIST_BAD")
 files={n for n in names if n!="capture_receipts.json" and not n.endswith("/")}
 if len(files)!=len(receipts):raise ValueError("TDCC_CAPTURE_MEMBER_COUNT_BAD")
 matched=set();details=[]
 for receipt in receipts:
  if not isinstance(receipt,dict) or receipt.get("source")!="TDCC_ARCHIVE" or receipt.get("dataset")!="holding_distribution":
   raise ValueError("TDCC_CAPTURE_SOURCE_DATASET_MISMATCH")
  if receipt.get("state")!="CAPTURED_ARCHIVE_STRUCTURE":
   raise ValueError("TDCC_CAPTURE_STATE_INVALID")
  origin=str(receipt.get("url",""))
  if not origin.startswith("https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/"):
   raise ValueError("TDCC_CAPTURE_UNEXPECTED_ORIGIN")
  path=receipt.get("file")
  if path not in files:raise ValueError("TDCC_CAPTURE_MEMBER_PATH_MISMATCH")
  if path in matched:raise ValueError("TDCC_CAPTURE_DUPLICATE_MEMBER")
  matched.add(path)
  raw=z.read(path)
  if receipt.get("sha256")!=sha(raw) or receipt.get("bytes")!=len(raw):
   raise ValueError("TDCC_CAPTURE_MEMBER_SHA_OR_SIZE")
  rows=records(raw,month)
  actual_dates={x["snapshot_date"] for x in rows}
  expected=dt.datetime.strptime(receipt.get("period",""),"%Y-%m-%d").date().isoformat()
  if actual_dates!={expected}:raise ValueError("TDCC_CAPTURE_RECEIPT_DATE_DIFF")
  if receipt.get("rows")!=len(rows):raise ValueError("TDCC_CAPTURE_ROW_COUNT_DIFF")
  details.append({"source":"TDCC_ARCHIVE_EXTERNAL_MIRROR","month":month,
    "observation_date":expected,"rows":len(rows),"native_csv_sha256":sha(raw),
    "original_url":origin,"official_pit_verified":False})
 if matched!=files:raise ValueError("TDCC_CAPTURE_UNDECLARED_MEMBERS")
 return details
