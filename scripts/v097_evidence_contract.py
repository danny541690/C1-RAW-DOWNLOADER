#!/usr/bin/env python3
"""JARVIS v0.97 immutable evidence contract and versioned dataset registry.

Historical formats are *not* inferred from today's API fields. Unknown dataset
versions fail closed. Pure deterministic comparison functions have regression
tests; no synthetic example is ever written as real evidence.
"""
import hashlib,json,re,sys,datetime
from decimal import Decimal,InvalidOperation

SOURCE_FAMILIES={
 "TWSE":{"STOCK_DAILY_OHLCV":("trade_date","stock_id","market")},
 "TPEx":{"STOCK_DAILY_OHLCV":("trade_date","stock_id","market")},
 "MOPS":{"FINANCIAL_STATEMENT":("company_id","filing_period","statement_type","account_code","revision")},
 "TDCC":{"SHAREHOLDING_DISTRIBUTION":("snapshot_date","security_id","security_class","holder_tier")},
 "TAIFEX":{"FUTURES_DAILY":("trade_date","contract","contract_month","session")},
 "NDC":{"MONTHLY_SERIES":("series","observation_month","revision")},
 "FinMind":{"TaiwanStockPrice":("date","stock_id")}
}
# The registry is intentionally partial. A concrete historical schema version,
# required fields and units must be sourced from a verified source document.
# Do not auto-fill historical columns based solely on a contemporary API page.
VERSION="v097_evidence_contract_1"
HASH=re.compile(r"[0-9a-f]{64}\Z")
def sha256(data):
 if not isinstance(data,(bytes,bytearray)):raise TypeError("BYTE_PAYLOAD_REQUIRED")
 return hashlib.sha256(data).hexdigest()
def canon_decimal(value):
 if value is None:return None
 if isinstance(value,bool):raise ValueError("BOOLEAN_NOT_NUMERIC")
 try:
  x=Decimal(str(value).replace(",",""))
  if not x.is_finite():raise ValueError("NAN_OR_INFINITY")
  return format(x.normalize(),"f")
 except (InvalidOperation,ValueError,TypeError) as exc:
  raise ValueError("UNRECOGNIZED_NUMERIC_VALUE") from exc
def canonical_value(value,field,numeric_fields):
 if field in numeric_fields:return canon_decimal(value)
 # Preserve zero vs null; dates and codes stay text (no rounding of IDs).
 return value
def digest_rows(rows,keys,fields,numeric_fields=()):
 """Compare ALL cells under explicit schema. Never silently discard extra rows."""
 if not isinstance(rows,list) or not rows:raise ValueError("EMPTY_OR_INVALID_ROWS")
 if len(set(keys))!=len(keys) or len(set(fields))!=len(fields):raise ValueError("DUPLICATE_SCHEMA_FIELDS")
 if not set(keys).issubset(fields):raise ValueError("MISSING_KEY_IN_SCHEMA")
 data=[];keyset=set()
 for row in rows:
  if not isinstance(row,dict) or set(row)!=set(fields):
   raise ValueError("MISSING_OR_EXTRA_COLUMNS")
  key=tuple(str(row[k]) for k in keys)
  if key in keyset:raise ValueError("DUPLICATE_BUSINESS_KEY")
  keyset.add(key)
  data.append((key,{f:canonical_value(row[f],f,numeric_fields) for f in fields}))
 data.sort(key=lambda x:x[0])
 payload=json.dumps([v for _,v in data],ensure_ascii=False,sort_keys=True,
    separators=(",",":"),allow_nan=False).encode("utf-8")
 return {"row_count":len(rows),"digest":sha256(payload),"keys_sha256":sha256(
  json.dumps([k for k,_ in data],ensure_ascii=False,separators=(",",":")).encode())}
def compare_three_complete(original,official,third,keys,fields,numeric_fields):
 a=digest_rows(original,keys,fields,numeric_fields)
 b=digest_rows(official,keys,fields,numeric_fields)
 c=digest_rows(third,keys,fields,numeric_fields)
 if len({a["row_count"],b["row_count"],c["row_count"]})!=1:
  return {"status":"HOLD_ROW_COUNT_MISMATCH","row_counts":[a["row_count"],b["row_count"],c["row_count"]]}
 if len({a["keys_sha256"],b["keys_sha256"],c["keys_sha256"]})!=1:
  return {"status":"HOLD_BUSINESS_KEY_MISMATCH","row_counts":[a["row_count"],b["row_count"],c["row_count"]]}
 if len({a["digest"],b["digest"],c["digest"]})!=1:
  return {"status":"HOLD_FULL_FILE_VALUE_MISMATCH","row_counts":[a["row_count"],b["row_count"],c["row_count"]]}
 return {"status":"FULL_FILE_THREE_WAY_VALUES_MATCHED","row_count":a["row_count"],
   "canonical_digest":a["digest"],"all_rows_compared":True,"all_columns_compared":True}
def verify_pit(published_at,asof):
 def dt(s):
  if not isinstance(s,str):raise ValueError("PIT_TIMESTAMP_REQUIRED")
  z=datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
  if z.tzinfo is None:raise ValueError("PIT_MISSING_TIMEZONE")
  return z.astimezone(datetime.timezone.utc)
 return dt(published_at)<=dt(asof)
def safe_evidence_claim(e,source_id,original_sha):
 """Validate existing external proof claims; do not trust a fabricated flag."""
 if not isinstance(e,dict) or e.get("source_id")!=source_id or e.get("original_sha256")!=original_sha:
  return "HOLD_EVIDENCE_ID_SHA_MISMATCH"
 for k in ("official_response_sha256","third_party_response_sha256",
    "original_row_digest","official_row_digest","third_party_row_digest"):
  if not HASH.fullmatch(str(e.get(k,""))):return "HOLD_REQUIRED_RESPONSE_OR_ROW_HASH_MISSING"
 if len({e["original_row_digest"],e["official_row_digest"],e["third_party_row_digest"]})!=1:
  return "HOLD_CANONICAL_FULL_FILE_DIGEST_DIFFER"
 if not all(e.get(k) is True for k in ("all_rows_verified","all_fields_verified","publication_pit_verified")):
  return "HOLD_PROOF_FLAGS_OR_PIT_MISSING"
 for k in ("official_fetch_receipt_id","third_party_fetch_receipt_id","original_extracted_value_receipt_id",
           "schema_version_id","dataset","source_uri_asof","official_published_at","publication_pit_as_of"):
  if not e.get(k):return "HOLD_MISSING_INDEPENDENT_RECEIPT_OR_SCHEMA"
 if not verify_pit(e["official_published_at"],e["publication_pit_as_of"]):
  return "HOLD_LOOKAHEAD_PUBLICATION"
 # Claim is still NOT proof until the release verifier independently fetches
 # referenced actual bytes, recomputes every digest and validates source lineage.
 return "REVIEW_CLAIM_ONLY_NOT_SIGNED"
def selftest():
 fields=("trade_date","stock_id","market","close","volume")
 r=[{"trade_date":"2025-01-02","stock_id":"2330","market":"TSE","close":"100.00","volume":"1000"},
    {"trade_date":"2025-01-02","stock_id":"2317","market":"TSE","close":"80","volume":"500"}]
 shuffled=list(reversed(r))
 t=compare_three_complete(r,shuffled,r,("trade_date","stock_id","market"),fields,("close","volume"))
 assert t["status"]=="FULL_FILE_THREE_WAY_VALUES_MATCHED"
 different=[dict(x) for x in r];different[1]["close"]="101"
 assert compare_three_complete(r,different,r,("trade_date","stock_id","market"),fields,("close","volume"))["status"]=="HOLD_FULL_FILE_VALUE_MISMATCH"
 assert compare_three_complete(r,r[:1],r,("trade_date","stock_id","market"),fields,("close","volume"))["status"]=="HOLD_ROW_COUNT_MISMATCH"
 for bad in ([dict(r[0],extra="1")], [r[0],r[0]]):
  try:digest_rows(bad,("trade_date","stock_id","market"),fields,("close",))
  except ValueError:pass
  else:raise AssertionError("STRICT_SCHEMA_DID_NOT_REJECT")
 assert not verify_pit("2026-11-16T09:00:00Z","2026-11-15T09:00:00Z")
 assert safe_evidence_claim({},"x","a"*64).startswith("HOLD")
 assert set(SOURCE_FAMILIES)=={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind"}
 print("EVIDENCE_CONTRACT_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 else:raise SystemExit("usage: selftest")
