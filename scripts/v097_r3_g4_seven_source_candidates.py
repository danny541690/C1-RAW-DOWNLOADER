"""Seven-source G4 input catalog seed, no Silver transformation or approval.

Source-specific primary keys from G2/G3 historic contract catalog are mapped
to proposed Silver INPUT semantic keys. Every template starts with HOLD and
cannot be used to issue a formal G4 certificate.
"""
from __future__ import annotations
import json,sys
from scripts.v097_g2g3_formal_contracts_v2 import KEY_SCHEMAS
from scripts.v097_r3_gate_core import SOURCES,digest

SOURCE_SEMANTIC={
"TWSE":{"date":"trade_date","code":"security_id","index_id":"index_id","investor_type":"institution_type"},
"TPEx":{"date":"trade_date","code":"security_id","index_id":"index_id"},
"MOPS":{"period":"accounting_period","code":"security_id","statement_item":"statement_item","filing_revision":"publication_revision"},
"TDCC":{"date":"effective_date","effective_date":"effective_date","code":"security_id","tier":"holder_tier"},
"TAIFEX":{"date":"trade_date","contract":"contract_id","expiration":"expiration","session":"trading_session","strike":"strike_price","put_call":"option_type"},
"NDC":{"period":"period","series_id":"series_id","component_id":"component_id"},
"FinMind":{"date":"trade_date","period":"accounting_period","code":"security_id","statement_item":"statement_item"}}
def catalog():
    items=[]
    for src in SOURCES:
        for dataset,keys in KEY_SCHEMAS[src].items():
            known=SOURCE_SEMANTIC[src]
            if any(k not in known for k in keys):raise ValueError("UNMAPPED_KEY_"+src+"_"+dataset)
            items.append({"source":src,"dataset":dataset,"primary_key_semantics":list(keys),
                          "proposed_target_keys":{k:known[k] for k in keys},
                          "certification_status":"HOLD_G2_G3_OFFICIAL_SEMANTICS",
                          "source_type_version":"UNATTESTED",
                          "unit_conversions":"REQUIRE_NATIVE_DATASET_PROOF",
                          "publication_pit":"REQUIRE_SOURCE_RELEASE_PROOF",
                          "security_identity":"REQUIRE_HISTORIC_SCOPE_PROOF",
                          "materialized":False})
    return {"schema":"R3_G4_SEVEN_SOURCE_CANDIDATE_CATALOG_V1","count":len(items),
            "source_count":len(SOURCES),"verified":0,"materialized":False,
            "catalog_hash":digest(items),"templates":items}

def selftest():
    x=catalog()
    assert {r["source"] for r in x["templates"]}==set(SOURCES)
    assert len(x["templates"])>=15
    assert all(r["certification_status"].startswith("HOLD") and not r["materialized"] for r in x["templates"])
    print("R3_G4_SEVEN_SOURCE_CANDIDATES="+json.dumps({"templates":x["count"],"hash":x["catalog_hash"],"approved":0},sort_keys=True))

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["catalog"]:print(json.dumps(catalog(),sort_keys=True,ensure_ascii=False))
    else:raise SystemExit("selftest|catalog")
