#!/usr/bin/env python3
"""R16 deterministic concurrent-claim and failure-recovery test, synthetic only.
Cross-GitHub-Run production transaction/Drive consistency remains unproven.
"""
import argparse,concurrent.futures,json,multiprocessing,pathlib,sqlite3,tempfile
from v098_r9_ledger_fault_injection import db,seed,claim,finish,SOURCES
def _claim(args):
    path,source,worker,clock=args
    conn=db(path)
    try:return claim(conn,source,worker,clock)
    finally:conn.close()
def run(out):
    with tempfile.TemporaryDirectory() as d:
        f=str(pathlib.Path(d)/"master.sqlite");conn=db(f);seed(conn);conn.close()
        tasks=[(f,"TWSE",f"worker-{i}",1000) for i in range(12)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=12) as pool:
            winners=list(pool.map(_claim,tasks))
        nonnull=[x for x in winners if x is not None]
        assert len(nonnull)==1, "more than one worker claimed the same task"
        old=nonnull[0]
        conn=db(f)
        late=claim(conn,"TWSE","recovery",1121)
        assert late is not None and late[3]==2
        assert not finish(conn,old,1122)
        assert finish(conn,late,1123)
        assert claim(conn,"TWSE","duplicate",9999) is None
        conn.close()
        again=db(f)
        assert again.execute("SELECT COUNT(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0]==1
        assert again.execute("SELECT COUNT(*) FROM attempts WHERE task_key=?",(old[0],)).fetchone()[0]==2
        again.close()
        result={"status":"PASS","scope":"REAL_PARALLEL_PROCESSES_LOCAL_SQLITE",
          "claimants":12,"simultaneous_winners":1,"lease_takeover_generation":2,
          "stale_lease_results_rejected":1,"completed_unique_tasks":1,
          "restart_duplicate_attempts":0,"production_remote_atomic_CAS":False}
        path=pathlib.Path(out);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);run(p.parse_args().out)
