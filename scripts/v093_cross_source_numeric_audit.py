"""Exact-key, read-only cross-source numeric comparison.

Never infer that native fields with different names or units mean the same
metric. Report comparisons only for explicitly mapped semantics and proven units.
"""
import collections,datetime,math,re
# Explicit names only. No speculative financial field mappings.
PRICE_FIELDS={
 "open":{"FinMind":"open","TWSE":"開盤價","TPEx":"開盤價"},
 "high":{"FinMind":"max","TWSE":"最高價","TPEx":"最高價"},
 "low":{"FinMind":"min","TWSE":"最低價","TPEx":"最低價"},
 "close":{"FinMind":"close","TWSE":"收盤價","TPEx":"收盤價"},
}
def matches_native_field(native_field,expected):
 """Array-field suffixes preserve original column positions; never use substrings."""
 return native_field==expected or bool(re.fullmatch(re.escape(expected)+r"__col_\d{1,4}",str(native_field or "")))

def is_mapped_native_field(source,metric,native_field):
 expected=PRICE_FIELDS.get(metric,{}).get(source)
 if expected and matches_native_field(native_field,expected):return True
 # TPEx daily tables explicitly label OHLC 開盤/最高/最低/收盤.
 # Match only these complete labels, never ex-dividend or reference fields.
 aliases={"open":"開盤","high":"最高","low":"最低","close":"收盤"}
 return source=="TPEx" and metric in aliases and matches_native_field(native_field,aliases[metric])

def compare_rows(rows_by_source,metric="close",abs_tol=0.01):
 if metric not in PRICE_FIELDS:raise ValueError("METRIC_NOT_MAPPED")
 if isinstance(abs_tol,bool) or not isinstance(abs_tol,(int,float)) or not math.isfinite(abs_tol) or abs_tol<0:
  raise ValueError("INVALID_ABSOLUTE_TOLERANCE")
 mapping=PRICE_FIELDS[metric]
 values={};conflicts=set();unmapped=collections.Counter()
 for source,rows in rows_by_source.items():
  field=mapping.get(source)
  if not field:
   unmapped[source]+=len(rows);continue
  for r in rows:
   if not is_mapped_native_field(source,metric,r.get("native_field")):
    continue
   if r.get("source")!=source or not r.get("date") or not r.get("stock_id"):
    unmapped[source]+=1;continue
   try:
    if datetime.date.fromisoformat(r["date"]).isoformat()!=r["date"]:raise ValueError("NONCANONICAL_DATE")
   except (TypeError,ValueError):
    unmapped[source]+=1;continue
   if not isinstance(r["stock_id"],str) or not re.fullmatch(r"[0-9A-Za-z]{4,8}",r["stock_id"]):
    unmapped[source]+=1;continue
   val=r.get("numeric_unscaled")
   if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val):
    unmapped[source]+=1;continue
   key=(r["date"],r["stock_id"])
   bucket=values.setdefault(key,{})
   conflict_key=(key,source)
   if conflict_key in conflicts:continue
   if source in bucket and bucket[source]!=float(val):
    conflicts.add(conflict_key)
    del bucket[source]
   else:bucket[source]=float(val)
 pairs=collections.Counter();matches=collections.Counter();mismatches=collections.Counter();examples=[]
 for key,bucket in values.items():
  src=sorted(bucket)
  for i,a in enumerate(src):
   for b in src[i+1:]:
    pair=a+"__"+b
    pairs[pair]+=1
    if math.isclose(bucket[a],bucket[b],rel_tol=0,abs_tol=abs_tol):
     matches[pair]+=1
    else:
     mismatches[pair]+=1
     if len(examples)<8:examples.append({"date":key[0],"stock_id":key[1],"pair":pair,"left":bucket[a],"right":bucket[b]})
 return {"metric":metric,"candidate_keys":len(values),"compared_pairs":dict(pairs),
         "within_tolerance":dict(matches),"mismatch":dict(mismatches),
         "duplicate_conflicts":len(conflicts),"unmapped":dict(unmapped),
         "conflict_policy":"EXCLUDE_CONFLICTED_SOURCE_KEY",
         "mismatch_examples":examples,"independent_numeric_verified":False,
         "unit_verified":False,"pit_verified":False,"certified":False}
