#!/usr/bin/env python3
"""JARVIS v0.98 R8: centrally issued synthetic six-source ledger contract.

SAFETY: no external API, no Drive access, no real market data, no migration.
Production requires a durable transactional ledger, CAS/fencing across runs,
validated source coverage, real workers and source/target SHA256 evidence.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
import tempfile

SOURCES = ("TWSE", "TPEx", "MOPS", "NDC", "TDCC", "TAIFEX")
EVENTS = ("DISPATCH_RECEIVED", "EXECUTION_STARTED", "EXECUTION_FINISHED")
def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")
def digest(src, dataset, period, operation):
    return hashlib.sha256(json.dumps([src,dataset,period,operation],separators=(",",":")).encode()).hexdigest()
def put(p, obj):
    path=pathlib.Path(p);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2),encoding="utf-8")
def read(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def plan(out,run_id):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    tasks=[]
    for src in SOURCES:
        job={"source":src,"dataset":"SYNTHETIC_CONTRACT_TEST","period":"2000-01",
             "operation":"INVENTORY_DRY_RUN","run_id":run_id,"generation":1,
             "dispatched_at":utc(),"synthetic_only":True}
        job["task_key"]=digest(src,job["dataset"],job["period"],job["operation"])
        job["attempt_id"]=f"{run_id}:{src}:1"
        put(out/(src+".json"),job);tasks.append(job)
    put(out/"plan_manifest.json",{"run_id":run_id,"tasks":len(tasks),
                                  "sources":list(SOURCES),"synthetic_only":True})
    return tasks
def worker(source,dispatch_dir,receipts_dir):
    job=read(pathlib.Path(dispatch_dir)/(source+".json"))
    if source not in SOURCES or job["source"]!=source or not job["synthetic_only"]:
        raise RuntimeError("Unauthorized source dispatch")
    assert job["task_key"]==digest(source,job["dataset"],job["period"],job["operation"])
    assert job["attempt_id"]==f'{job["run_id"]}:{source}:{job["generation"]}'
    events=[]
    for et in EVENTS:
        record={"event":et,"at":utc(),"source":source,"task_key":job["task_key"],
                "attempt_id":job["attempt_id"],"run_id":job["run_id"],
                "generation":job["generation"],"synthetic_only":True}
        if et=="EXECUTION_FINISHED":
            record["status"]="PASS_DRY_RUN"
            record["evidence"]={"real_drive_access":False,"files_written":0}
        events.append(record)
    put(pathlib.Path(receipts_dir)/(source+".json"),{"dispatch":job,"events":events})
    return events
def init(conn):
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks(
      task_key TEXT PRIMARY KEY,source TEXT NOT NULL,status TEXT NOT NULL,
      generation INTEGER NOT NULL,attempt_id TEXT,committed_at TEXT);
    CREATE TABLE IF NOT EXISTS attempts(
      attempt_id TEXT PRIMARY KEY,task_key TEXT NOT NULL,started_at TEXT NOT NULL,
      finished_at TEXT NOT NULL,status TEXT NOT NULL,
      FOREIGN KEY(task_key) REFERENCES tasks(task_key));
    CREATE TABLE IF NOT EXISTS events(
      attempt_id TEXT NOT NULL,event TEXT NOT NULL,occurred_at TEXT NOT NULL,payload TEXT NOT NULL,
      PRIMARY KEY(attempt_id,event));
    """)
def reconcile(dispatch_dir,receipts_dir,db,report):
    manifest=read(pathlib.Path(dispatch_dir)/"plan_manifest.json")
    if manifest["sources"]!=list(SOURCES) or manifest["tasks"]!=6 or not manifest["synthetic_only"]:
        raise RuntimeError("Invalid central manifest")
    dispatch_files={p.stem for p in pathlib.Path(dispatch_dir).glob("*.json") if p.name!="plan_manifest.json"}
    receipt_files={p.stem for p in pathlib.Path(receipts_dir).glob("*.json")}
    if dispatch_files!=set(SOURCES) or receipt_files!=set(SOURCES):
        raise RuntimeError("Missing/extra source accounts or assignments")
    db=pathlib.Path(db);db.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(db)
    init(conn)
    results=[]
    try:
        for src in SOURCES:
            assignment=read(pathlib.Path(dispatch_dir)/(src+".json"))
            receipt=read(pathlib.Path(receipts_dir)/(src+".json"))
            if receipt["dispatch"]!=assignment:
                raise RuntimeError(f"{src}: altered or stale dispatch")
            if assignment["run_id"]!=manifest["run_id"] or assignment["source"]!=src:
                raise RuntimeError(f"{src}: central run/source mismatch")
            if assignment["task_key"]!=digest(src,assignment["dataset"],assignment["period"],assignment["operation"]):
                raise RuntimeError(f"{src}: invalid task key")
            if assignment["generation"]<1 or assignment["attempt_id"]!=f'{assignment["run_id"]}:{src}:{assignment["generation"]}':
                raise RuntimeError(f"{src}: invalid fencing generation")
            events=receipt["events"]
            if len(events)!=3 or [e.get("event") for e in events]!=list(EVENTS):
                raise RuntimeError(f"{src}: invalid event life cycle")
            for e in events:
                for field in ("source","task_key","attempt_id","run_id","generation"):
                    if e.get(field)!=assignment[field]:
                        raise RuntimeError(f"{src}: inconsistent {field}")
                if not e.get("synthetic_only"):
                    raise RuntimeError(f"{src}: non synthetic event")
            times=[dt.datetime.fromisoformat(e["at"]) for e in events]
            if any(t.tzinfo is None for t in times) or not(times[0]<=times[1]<=times[2]):
                raise RuntimeError(f"{src}: invalid event timestamps")
            if events[-1].get("status")!="PASS_DRY_RUN" or events[-1].get("evidence")!={"real_drive_access":False,"files_written":0}:
                raise RuntimeError(f"{src}: invalid success evidence")
            with conn:
                # The reconciler is the sole writer. A production deployment additionally
                # needs a durable shared CAS/lease and cannot reuse this local ephemeral DB.
                cur=conn.execute("SELECT status,generation,attempt_id FROM tasks WHERE task_key=?",(assignment["task_key"],)).fetchone()
                if cur and cur[0]=="COMMITTED":
                    results.append({"source":src,"status":"SKIP_ALREADY_COMMITTED"})
                    continue
                if cur and cur[1]>assignment["generation"]:
                    raise RuntimeError(f"{src}: stale generation rejected")
                if not cur:
                    conn.execute("INSERT INTO tasks(task_key,source,status,generation,attempt_id) VALUES(?,?,?,?,?)",
                                 (assignment["task_key"],src,"PENDING",assignment["generation"],assignment["attempt_id"]))
                else:
                    conn.execute("UPDATE tasks SET generation=?,attempt_id=? WHERE task_key=? AND status='PENDING'",
                                 (assignment["generation"],assignment["attempt_id"],assignment["task_key"]))
                conn.execute("INSERT OR IGNORE INTO attempts(attempt_id,task_key,started_at,finished_at,status) VALUES(?,?,?,?,?)",
                             (assignment["attempt_id"],assignment["task_key"],events[1]["at"],events[2]["at"],events[-1]["status"]))
                for e in events:
                    conn.execute("INSERT OR IGNORE INTO events(attempt_id,event,occurred_at,payload) VALUES(?,?,?,?)",
                                 (e["attempt_id"],e["event"],e["at"],json.dumps(e,ensure_ascii=False,sort_keys=True)))
                count=conn.execute("UPDATE tasks SET status='COMMITTED',committed_at=? WHERE task_key=? AND status='PENDING' AND generation=? AND attempt_id=?",
                                   (utc(),assignment["task_key"],assignment["generation"],assignment["attempt_id"])).rowcount
                if count!=1:raise RuntimeError(f"{src}: fencing/CAS rejection")
                results.append({"source":src,"status":"COMMITTED_DRY_RUN"})
        summary={"run_id":manifest["run_id"],"mode":"SYNTHETIC_ONLY","tasks":conn.execute("SELECT count(*) FROM tasks").fetchone()[0],
                 "committed":conn.execute("SELECT count(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0],
                 "attempts":conn.execute("SELECT count(*) FROM attempts").fetchone()[0],
                 "events":conn.execute("SELECT count(*) FROM events").fetchone()[0],
                 "sources":results,"real_market_data_processed":False,"finished_at":utc()}
        put(report,summary)
        if (summary["tasks"],summary["committed"],summary["events"],summary["attempts"])!=(6,6,18,6):
            raise RuntimeError("Master/source account reconciliation mismatch")
        return summary
    finally:conn.close()
def selftest(report):
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); dispatch=root/"dispatch"; receipts=root/"receipts"
        plan(dispatch,"R8-SELFTEST")
        for s in SOURCES:worker(s,dispatch,receipts)
        db=root/"master.db"
        first=reconcile(dispatch,receipts,db,root/"first.json")
        replay=reconcile(dispatch,receipts,db,root/"replay.json")
        assert all(r["status"]=="COMMITTED_DRY_RUN" for r in first["sources"])
        assert all(r["status"]=="SKIP_ALREADY_COMMITTED" for r in replay["sources"])
        tampered=read(receipts/"TWSE.json");tampered["events"][1]["task_key"]="bad"
        put(receipts/"TWSE.json",tampered)
        try:reconcile(dispatch,receipts,db,root/"tampered.json")
        except RuntimeError:pass
        else:raise AssertionError("Tampered event was accepted")
        (receipts/"TWSE.json").unlink()
        try:reconcile(dispatch,receipts,db,root/"missing.json")
        except RuntimeError:pass
        else:raise AssertionError("Missing receipt was accepted")
        put(report,{"status":"PASS","synthetic_only":True,
                    "tests":["central dispatch required","six distinct source accounts",
                             "event lifecycle and timestamps","tampered receipt rejected",
                             "missing receipt rejected","single reconciler commit",
                             "same-DB replay idempotence","no real data access"],
                    "limitation":"Cross-run persistence/lease, Drive publication and production migration NOT tested"})
def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("plan","worker","reconcile","selftest"))
    p.add_argument("--source",choices=SOURCES)
    p.add_argument("--dispatch",default="dispatch")
    p.add_argument("--receipts",default="receipts")
    p.add_argument("--run-id",default="R8-LOCAL")
    p.add_argument("--db",default="master.sqlite")
    p.add_argument("--report",default="result.json")
    a=p.parse_args()
    if a.mode=="plan":plan(a.dispatch,a.run_id)
    elif a.mode=="worker":
        if not a.source:p.error("--source required")
        worker(a.source,a.dispatch,a.receipts)
    elif a.mode=="reconcile":reconcile(a.dispatch,a.receipts,a.db,a.report)
    else:selftest(a.report)
if __name__=="__main__":main()
