#!/usr/bin/env python3
"""JARVIS v0.97 R1: fail-closed G0->G4 acceptance, no Bronze writes or Silver/Gold.
Single file-level state machine; reusable immutable evidence is checked against SHA,
contract and parser revisions. Only formally attested G2/G3 evidence can release G4.
"""
import collections
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

VERSION = "v097_acceptance_r1_20261118_01"
TARGET = 74750
COUNTS = {"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,
          "TAIFEX":3140,"NDC":320,"FinMind":3700}
SHARDS = {"TWSE":2,"TPEx":2,"MOPS":1,"TDCC":6,"TAIFEX":1,"NDC":1,"FinMind":1}
RUN = os.getenv("GITHUB_RUN_ID","manual")
BATCH = max(1,min(500,int(os.getenv("R1_BATCH","200"))))
CHECKPOINT = "v097_R1_ACCEPTANCE_CK_"
CERT_G2 = "v097_R1_G2_CERT_"
CERT_G3 = "v097_R1_G3_CERT_"
GOOD_G1 = {"SCHEMA_PROFILED_NEEDS_MAPPING","SCHEMA_INPUT_READY",
           "FORMAT_PROFILED","FORMAT_PASSED"}
BLOCKED_G1 = {"FORMAT_STRUCTURAL_HOLD","SOURCE_READ_FAILED_FINAL","BLOCKED_BRONZE"}
TERMINAL = {"READY","EXCLUDED","CONFIRMED_EXCEPTION"}
def canon(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)
def digest(v):
    return hashlib.sha256(canon(v).encode()).hexdigest()
def now():
    return datetime.now(timezone.utc).isoformat()
def lane(sid, source):
    return int(hashlib.sha256(sid.encode()).hexdigest(),16)%SHARDS[source]
def is_sha(s):
    return isinstance(s,str) and len(s)==64 and all(c in "0123456789abcdef" for c in s.lower())
def scope(row):
    # A scope decision is independent of the file's integrity or source identity.
    return row.get("scope_status") or row.get("stock_scope") or "UNKNOWN"
def valid_proof(proof,row,kind,era=None,dataset=None):
    if not isinstance(proof,dict) or proof.get("schema") != kind:
        return False
    if proof.get("source_id")!=row.get("source_id") or proof.get("source")!=row.get("source"):
        return False
    if proof.get("sha")!=row.get("source_sha256") or not is_sha(proof.get("sha")):
        return False
    if not proof.get("contract_version") or not proof.get("evidence_sha256"):
        return False
    if not is_sha(proof["evidence_sha256"]):
        return False
    if not proof.get("official_reference") or not proof.get("official_evidence_id"):
        return False
    if proof.get("official_attested") is not True:
        return False
    if era is not None and proof.get("era")!=era:
        return False
    if dataset is not None and proof.get("dataset")!=dataset:
        return False
    return True
def evaluate(row,fmt,mp,v3,g2,g3,era=None):
    sid=row.get("source_id")
    src=row.get("source")
    sha=row.get("source_sha256")
    evidence={}
    if not sid or src not in COUNTS or not is_sha(sha) or not row.get("destination_id"):
        return {"status":"CONFIRMED_EXCEPTION","reason":"INVALID_FROZEN_ID_SHA_DESTINATION",
                "gates":dict.fromkeys(("G0","G1","G2","G3","G4"),"BLOCKED"),"source_id":sid}
    g0="PENDING";g1="PENDING";g2state="PENDING";g3state="PENDING";g4="PENDING"
    reason="G0_READBACK_PENDING"
    if row.get("bronze_status")!="BRONZE_INTEGRITY_READY":
        g0="HOLD";reason="BRONZE_BASELINE_LINEAGE_NOT_CERTIFIED"
    elif isinstance(v3,dict) and v3.get("sha")==sha and v3.get("g0") in ("DEST_SHA_VERIFIED","DEST_SHA_VERIFIED_REUSED"):
        g0="PASS";evidence["G0"]=v3.get("run")
    if g0=="PASS":
        if (isinstance(fmt,dict) and fmt.get("sha")==sha and fmt.get("status") in GOOD_G1 and
            not (isinstance(v3,dict) and v3.get("sha")==sha and
                 v3.get("new_native_evidence",{}).get("format")=="ZIP" and
                 v3["new_native_evidence"].get("member_schemas_verified") is False)):
            g1="PASS";evidence["G1"]=fmt.get("contract_version")
        elif isinstance(v3,dict) and v3.get("sha")==sha and v3.get("g1") in ("SOURCE_FORMAT_PROFILED","ZIP_MEMBERS_PROFILED"):
            # ZIP member hashing/profile is useful, not complete member-level schema certification.
            g1="CANDIDATE";reason="G1_FULL_NATIVE_FORMAT_CERT_PENDING"
        elif isinstance(fmt,dict) and fmt.get("sha")==sha and fmt.get("status") in BLOCKED_G1:
            g1="HOLD";reason="G1_STRUCTURAL_HOLD"
        else:
            reason="G1_FORMAT_PROOF_PENDING"
    if g0=="PASS" and g1=="PASS":
        dataset=g2.get("dataset") if isinstance(g2,dict) else None
        if valid_proof(g2,row,"R1_G2_DATASET_CERT_V1",era):
            if dataset and g2.get("dataset_origin_verified") is True and g2.get("publication_asof_verified") is True:
                g2state="PASS";evidence["G2"]=g2["contract_version"]
            else:reason="G2_DATASET_OR_PIT_ATTESTATION_MISSING"
        else:reason="G2_OFFICIAL_DATASET_CONTRACT_PENDING"
        if g2state=="PASS":
            if (valid_proof(g3,row,"R1_G3_SCHEMA_CERT_V1",era,dataset) and
                g3.get("dataset_contract_version")==g2["contract_version"] and
                g3.get("full_file_scanned") is True and
                g3.get("native_units_verified") is True and
                g3.get("types_and_keys_verified") is True and
                g3.get("row_count",0)>0 and
                g3.get("validation_errors")==0):
                g3state="PASS";evidence["G3"]=g3["contract_version"]
            else:reason="G3_FULL_NATIVE_SCHEMA_CERT_PENDING"
            if g3state=="PASS":
                if (scope(row)=="IN_SCOPE" and g2.get("source_lineage_verified") is True and
                    g3.get("official_numeric_verified") is True and g3.get("pit_verified") is True):
                    g4="READY";reason="FULL_CHAIN_CERTIFIED"
                elif scope(row) in ("EXCLUDED_CONTROL","SCOPE_EXCLUDED_NONSTOCK","STOCK_SCOPE_EXCLUDED"):
                    g4="EXCLUDED";reason="OUTSIDE_STOCK_SCOPE"
                else:reason="G4_RELEASE_PROOF_OR_SCOPE_PENDING"
    # Stock-scope exclusions do not count as ready and never imply official provenance PASS.
    status="READY" if g4=="READY" else ("EXCLUDED" if g4=="EXCLUDED" else
            "CONFIRMED_EXCEPTION" if g0=="HOLD" or g1=="HOLD" else "PENDING")
    return {"source_id":sid,"source":src,"sha":sha,"status":status,"reason":reason,
            "gates":{"G0":g0,"G1":g1,"G2":g2state,"G3":g3state,"G4":g4},
            "evidence":evidence,"version":VERSION}
def fingerprint(row,fmt,mp,v3,g2,g3,era):
    return digest({"sha":row.get("source_sha256"),"destination_id":row.get("destination_id"),
                   "fmt":fmt,"map":mp,"v3":v3,"g2":g2,"g3":g3,"era":era,
                   "scope":scope(row),"engine":VERSION})
def get_contracts(api,control,match,load_json,name,src):
    f=match(api,control,name+src+".json")
    if not f:return {}
    data=load_json(api,f["id"])
    if data.get("schema") not in ("R1_G2_DATASET_CERT_V1","R1_G3_SCHEMA_CERT_V1"):
        raise RuntimeError("CERTIFICATE_REGISTRY_SCHEMA_INVALID_"+src)
    done=data.get("done",{})
    if not isinstance(done,dict):raise RuntimeError("CERTIFICATE_REGISTRY_NOT_DICT_"+src)
    return done
def source(src,shard):
    if src not in COUNTS or not 0<=shard<SHARDS[src]:raise ValueError("BAD_SOURCE_OR_SHARD")
    from scripts.v097_bronze_autopilot import source_api
    from scripts.v097_v3_preflight import read_baseline,load_evidence,assert_cohort
    from scripts.v097_v3_unified_master import load_worker
    from scripts.v097_seven_historical_format_registry import period
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src)
    assert_cohort(rows,src)
    pick,maps=load_evidence(api,control,match,load_json,src,rows)
    workers=load_worker(api,control,match,load_json,src,rows)
    c2=get_contracts(api,control,match,load_json,CERT_G2,src)
    c3=get_contracts(api,control,match,load_json,CERT_G3,src)
    idx={r["source_id"]:r for r in rows}
    if (set(c2)-set(idx)) or (set(c3)-set(idx)):
        raise RuntimeError("CONTRACT_CERT_ORPHAN_"+src)
    name=CHECKPOINT+src+"_"+str(shard)+".json"
    f=match(api,control,name)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"shard":shard,"done":{}}
    if ck.get("schema")!=VERSION or ck.get("source")!=src or ck.get("shard")!=shard:
        raise RuntimeError("R1_CHECKPOINT_CONFLICT")
    done=ck["done"]
    queue=[r for r in rows if lane(r["source_id"],src)==shard]
    if set(done)-{r["source_id"] for r in queue}:raise RuntimeError("R1_CHECKPOINT_ORPHAN")
    changes={}
    for r in queue:
        sid=r["source_id"]
        f1=pick(r);mp=maps.get(sid);v3=workers.get(sid)
        historical=(f1 or {}).get("historical_version")
        # Historical edition may be derivable, but date parsing without proof is not certification.
        if not historical:
            ym=(r.get("data_date") or r.get("date") or "")[:7]
            if len(ym)==7:
                try:historical=period(src,ym)["id"]
                except (ValueError,KeyError,TypeError):pass
        p2=c2.get(sid);p3=c3.get(sid)
        # G0 is a real destination-byte verification, never inferred from legacy status.
        # Read only when no matching V3 destination SHA evidence is available.
        prior=done.get(sid)
        cached_g0=(prior or {}).get("g0_readback_sha") == r["source_sha256"]
        native=v3 if isinstance(v3,dict) else {}
        if cached_g0 and native.get("g0") not in ("DEST_SHA_VERIFIED","DEST_SHA_VERIFIED_REUSED"):
            native={**native,"sha":r["source_sha256"],"g0":"DEST_SHA_VERIFIED_REUSED","run":prior.get("run")}
        fp=fingerprint(r,f1,mp,native,p2,p3,historical)
        if prior and prior.get("fingerprint")==fp and prior.get("status")!="RETRY_PENDING":continue
        if prior and prior.get("status")=="RETRY_PENDING" and prior.get("attempts",0)>=3:continue
        if native.get("g0") not in ("DEST_SHA_VERIFIED","DEST_SHA_VERIFIED_REUSED"):
            try:
                blob=call(lambda:api.files().get_media(fileId=r["destination_id"]))
                if not blob:raise ValueError("EMPTY_DESTINATION")
                received=hashlib.sha256(blob).hexdigest()
                if received!=r["source_sha256"]:
                    raise ValueError("DESTINATION_SHA_MISMATCH")
                native={**native,"sha":r["source_sha256"],"g0":"DEST_SHA_VERIFIED",
                        "run":RUN}
            except Exception as exc:
                hard_error=isinstance(exc,ValueError)
                attempts=(prior or {}).get("attempts",0)+1
                state="CONFIRMED_EXCEPTION" if hard_error or attempts>=3 else "RETRY_PENDING"
                z={"source_id":sid,"source":src,"sha":r["source_sha256"],
                   "status":state,"reason":"G0_READBACK_"+type(exc).__name__,
                   "gates":{"G0":"HOLD" if hard_error else "PENDING","G1":"PENDING",
                            "G2":"PENDING","G3":"PENDING","G4":"PENDING"},
                   "attempts":attempts,"evidence":{},"version":VERSION,
                   "fingerprint":fp,"run":RUN,"at":now(),"era":historical}
                changes[sid]=z
                if len(changes)>=BATCH:break
                continue
        fp=fingerprint(r,f1,mp,native,p2,p3,historical)
        z=evaluate(r,f1,mp,native,p2,p3,historical)
        z.update({"fingerprint":fp,"run":RUN,"at":now(),"era":historical,
                  "g0_readback_sha":r["source_sha256"]})
        changes[sid]=z
        if len(changes)>=BATCH:break
    if changes:
        put_once(api,quality,"v097_R1_DELTA_"+src+"_"+str(shard)+"_"+RUN+".json",
                 {"schema":VERSION,"source":src,"shard":shard,"run":RUN,"rows":changes})
        done.update(changes)
        ck.update({"done":done,"last_run":RUN,"updated_at":now()})
        upsert(api,control,name,ck)
        witness=match(api,control,name)
        if not witness or len(load_json(api,witness["id"]).get("done",{}))!=len(done):
            raise RuntimeError("R1_CHECKPOINT_READBACK_FAILURE")
    states=collections.Counter(v["status"] for v in done.values())
    print("R1_PROGRESS="+canon({"source":src,"shard":shard,"cohort":len(queue),
         "evaluated":len(done),"new":len(changes),"not_evaluated":len(queue)-len(done),
         "status":dict(states)}),flush=True)
def aggregate():
    from scripts.v097_bronze_autopilot import source_api
    from scripts.v097_v3_preflight import read_baseline,assert_cohort
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    all_status=collections.Counter();results=[];total=0;ids=set()
    for src in COUNTS:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src)
        idx={r["source_id"]:r for r in rows}
        if ids & set(idx):raise RuntimeError("CROSS_SOURCE_DUPLICATE_ID")
        ids.update(idx)
        total+=len(rows)
        done={}
        for shard in range(SHARDS[src]):
            f=match(api,control,CHECKPOINT+src+"_"+str(shard)+".json")
            if not f:continue
            ck=load_json(api,f["id"])
            if ck.get("schema")!=VERSION:raise RuntimeError("R1_CHECKPOINT_VERSION_MISMATCH")
            for sid,v in ck.get("done",{}).items():
                if sid not in idx or sid in done or lane(sid,src)!=shard or v.get("sha")!=idx[sid]["source_sha256"]:
                    raise RuntimeError("R1_CHECKPOINT_SHA_OR_ID_CONFLICT")
                done[sid]=v
        counts=collections.Counter(done.get(r["source_id"],{}).get("status","NOT_EVALUATED") for r in rows)
        gate_counts={g:dict(collections.Counter(done.get(r["source_id"],{}).get("gates",{}).get(g,"NOT_EVALUATED") for r in rows)) for g in ("G0","G1","G2","G3","G4")}
        all_status.update(counts)
        results.append({"source":src,"cohort":len(rows),"status":dict(counts),"gates":gate_counts})
    if total!=TARGET or len(ids)!=TARGET or sum(all_status.values())!=TARGET:
        raise RuntimeError("R1_74750_ACCOUNTING_DRIFT")
    # Reuse the existing seven-source formal contract census; preserve its
    # candidate/official-proof distinction instead of silently inventing certificates.
    formal_file=match(api,control,"v097_G2G3_FORMAL_MASTER_LATEST.json")
    formal=load_json(api,formal_file["id"]) if formal_file else None
    formal_summary=None
    if formal is not None:
        if formal.get("cohort")!=TARGET or len(formal.get("sources",[]))!=len(COUNTS):
            raise RuntimeError("R1_FORMAL_CONTRACT_COHORT_CONFLICT")
        formal_names=[r.get("source") for r in formal["sources"]]
        if set(formal_names)!=set(COUNTS) or len(set(formal_names))!=len(COUNTS):
            raise RuntimeError("R1_FORMAL_SOURCE_ID_CONFLICT")
        formal_summary={"run":formal.get("run"),"report_id":formal.get("report_id"),
            "specs":formal.get("dataset_era_contract_count"),
            "groups":formal.get("group_count"),
            "blockers":formal.get("blocker_totals"),
            "g2_census_verified":formal.get("g2_verified",0),
            "g3_census_verified":formal.get("g3_verified",0),
            "note":"Official contract census is a candidate registry, not a per-file G2/G3 certificate."}
    master={"schema":VERSION,"run":RUN,"cohort":TARGET,"created_at":now(),
            "formal_contract_census":formal_summary,
            "status":dict(all_status),"sources":results,
            "evaluated":TARGET-all_status["NOT_EVALUATED"],
            "terminal_disposition":sum(all_status[t] for t in TERMINAL),
            "ready":all_status["READY"],"silver_materialized":0,"gold_materialized":0,
            "note":"Pending is not certified; historical READY is never promoted without G0-G4 full formal proof."}
    report_id=put_once(api,quality,"v097_R1_ACCEPTANCE_MASTER_"+RUN+".json",master)
    upsert(api,control,"v097_R1_ACCEPTANCE_MASTER_LATEST.json",{**master,"report_id":report_id})
    witness=match(api,control,"v097_R1_ACCEPTANCE_MASTER_LATEST.json")
    if not witness or load_json(api,witness["id"]).get("run")!=RUN:
        raise RuntimeError("R1_MASTER_READBACK_FAILED")
    print("R1_ACCEPTANCE_MASTER="+canon({**master,"report_id":report_id}),flush=True)
def preflight():
    from scripts.v097_bronze_autopilot import source_api
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    files=call(lambda:api.files().list(q="'"+control+"' in parents and trashed=false",
        fields="files(id,name),nextPageToken",pageSize=1))
    if not isinstance(files,dict):raise RuntimeError("DRIVE_AUTH_PROBE_FAILED")
    print("R1_OAUTH_READ_PREFLIGHT_PASS",flush=True)
def selftest():
    assert sum(COUNTS.values())==TARGET and sum(SHARDS.values())==14
    sha="a"*64
    row={"source_id":"TEST","source":"TWSE","source_sha256":sha,
         "destination_id":"D","bronze_status":"BRONZE_INTEGRITY_READY","stock_scope":"IN_SCOPE"}
    v3={"sha":sha,"g0":"DEST_SHA_VERIFIED","run":"R"}
    fmt={"sha":sha,"status":"SCHEMA_PROFILED_NEEDS_MAPPING","contract_version":"fmt-v1"}
    assert evaluate(row,fmt,None,v3,None,None)["gates"]=={"G0":"PASS","G1":"PASS","G2":"PENDING","G3":"PENDING","G4":"PENDING"}
    base={"source_id":"TEST","source":"TWSE","sha":sha,"official_reference":"https://www.twse.com.tw/",
          "official_evidence_id":"URI+SHA","official_attested":True,
          "contract_version":"dataset-v1","evidence_sha256":"b"*64,"era":"ERA","dataset":"STOCK_DAILY_OHLCV"}
    g2={**base,"schema":"R1_G2_DATASET_CERT_V1","dataset_origin_verified":True,
        "publication_asof_verified":True,"source_lineage_verified":True}
    g3={**base,"schema":"R1_G3_SCHEMA_CERT_V1","dataset_contract_version":"dataset-v1",
        "full_file_scanned":True,"native_units_verified":True,"types_and_keys_verified":True,
        "row_count":5,"validation_errors":0,"official_numeric_verified":True,"pit_verified":True}
    assert evaluate(row,fmt,None,v3,g2,g3,"ERA")["status"]=="READY"
    assert evaluate(row,fmt,None,v3,g2,{**g3,"full_file_scanned":False},"ERA")["status"]=="PENDING"
    assert evaluate(row,fmt,None,v3,{**g2,"sha":"x"*64},g3,"ERA")["gates"]["G2"]!="PASS"
    assert evaluate(row,fmt,None,{},g2,g3,"ERA")["status"]!="READY"
    assert evaluate({**row,"bronze_status":"BRONZE_INTEGRITY_HOLD"},fmt,None,v3,g2,g3,"ERA")["status"]!="READY"
    assert evaluate(row,fmt,None,v3,g2,g3,"OTHER_ERA")["status"]!="READY"
    assert evaluate({**row,"stock_scope":"STOCK_SCOPE_EXCLUDED"},fmt,None,v3,g2,g3,"ERA")["status"]=="EXCLUDED"
    zip_native={**v3,"new_native_evidence":{"format":"ZIP","member_schemas_verified":False}}
    assert evaluate(row,fmt,None,zip_native,g2,g3,"ERA")["status"]!="READY"
    assert all(0<=lane(str(i),src)<SHARDS[src] for src in SHARDS for i in range(10))
    print("R1_FAIL_CLOSED_E2E_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["preflight"]:preflight()
    elif sys.argv[1:]==["aggregate"]:aggregate()
    elif len(sys.argv)==3:source(sys.argv[1],int(sys.argv[2]))
    else:raise SystemExit("selftest|preflight|SOURCE SHARD|aggregate")
