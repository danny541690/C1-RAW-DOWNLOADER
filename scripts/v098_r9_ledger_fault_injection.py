#!/usr/bin/env python3
"""R9 standalone combined fault-injection gate: synthetic only, no external writes.
One-time bounded CI integration smoke verification.
"""
import json,sqlite3,hashlib,uuid,datetime as dt,tempfile,pathlib,argparse
SOURCES=("TWSE","TPEx","MOPS","NDC","TDCC","TAIFEX")
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def ident(s):return hashlib.sha256(json.dumps([s,"SYNTHETIC","2000-01","INVENTORY"]).encode()).hexdigest()
def db(path):
 c=sqlite3.connect(path,timeout=5,isolation_level=None);c.execute("PRAGMA busy_timeout=5000")
 c.executescript("""
 CREATE TABLE IF NOT EXISTS tasks(task_key TEXT PRIMARY KEY,source TEXT,status TEXT,epoch INTEGER DEFAULT 0,owner TEXT,lease_until REAL,committed TEXT);
 CREATE TABLE IF NOT EXISTS attempts(attempt TEXT PRIMARY KEY,task_key TEXT,epoch INTEGER,started TEXT,finished TEXT);
 CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,task_key TEXT,attempt TEXT,kind TEXT,at TEXT);
 """);return c
def event(c,k,a,name):c.execute("INSERT INTO events VALUES(?,?,?,?,?)",(uuid.uuid4().hex,k,a,name,now()))
def seed(c):
 c.execute("BEGIN IMMEDIATE")
 try:
  for s in SOURCES:c.execute("INSERT OR IGNORE INTO tasks(task_key,source,status) VALUES(?,?,?)",(ident(s),s,"PENDING"))
  c.execute("COMMIT")
 except:c.execute("ROLLBACK");raise
def claim(c,s,worker,clock):
 k=ident(s);c.execute("BEGIN IMMEDIATE")
 try:
  v=c.execute("SELECT status,epoch,lease_until FROM tasks WHERE task_key=?",(k,)).fetchone()
  if v is None:raise ValueError("unknown task")
  if v[0]=="COMMITTED" or (v[0]=="RUNNING" and v[2]>clock):
   c.execute("COMMIT");return None
  epoch=v[1]+1;attempt=f"{s}-{epoch}-{uuid.uuid4().hex[:8]}"
  c.execute("UPDATE tasks SET status='RUNNING',epoch=?,owner=?,lease_until=? WHERE task_key=?",(epoch,worker,clock+120,k))
  c.execute("INSERT INTO attempts VALUES(?,?,?,?,?)",(attempt,k,epoch,now(),None))
  event(c,k,attempt,"DISPATCHED");event(c,k,attempt,"STARTED")
  c.execute("COMMIT");return(k,s,worker,epoch,attempt)
 except:c.execute("ROLLBACK");raise
def finish(c,a,clock):
 k,s,worker,epoch,attempt=a;c.execute("BEGIN IMMEDIATE")
 try:
  v=c.execute("SELECT status,epoch,owner,lease_until FROM tasks WHERE task_key=?",(k,)).fetchone()
  valid=v and v[0]=="RUNNING" and v[1]==epoch and v[2]==worker and v[3]>=clock
  if not valid:
   event(c,k,attempt,"STALE_REJECTED");c.execute("COMMIT");return False
  n=c.execute("UPDATE tasks SET status='COMMITTED',committed=?,owner=NULL,lease_until=NULL WHERE task_key=? AND epoch=? AND status='RUNNING'",(now(),k,epoch)).rowcount
  if n!=1:raise RuntimeError("fencing failure")
  c.execute("UPDATE attempts SET finished=? WHERE attempt=?",(now(),attempt))
  event(c,k,attempt,"FINISHED");event(c,k,attempt,"COMMITTED");c.execute("COMMIT");return True
 except:c.execute("ROLLBACK");raise
def smoke(out):
 with tempfile.TemporaryDirectory() as d:
  path=pathlib.Path(d)/"master.sqlite";a=db(path);seed(a);b=db(path)
  first=claim(a,"TWSE","W1",1000);assert first
  assert claim(b,"TWSE","W2",1001) is None
  second=claim(b,"TWSE","W2",1121);assert second and second[3]==2
  assert not finish(a,first,1122)
  assert finish(b,second,1123)
  assert claim(a,"TWSE","W1",1200) is None
  for s in SOURCES[1:]:
   x=claim(a,s,"W-"+s,1000);assert x and finish(a,x,1002)
  a.close();b.close();c=db(path)
  counts={"tasks":c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
          "committed":c.execute("SELECT COUNT(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0],
          "attempts":c.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
          "stale_rejected":c.execute("SELECT COUNT(*) FROM events WHERE kind='STALE_REJECTED'").fetchone()[0]}
  assert counts=={"tasks":6,"committed":6,"attempts":7,"stale_rejected":1},counts
  for s in SOURCES:assert claim(c,s,"RESTART",1300) is None
  c.close()
  result={"status":"PASS","scope":"SYNTHETIC_LOCAL_SQLITE_ONLY","counts":counts,
          "tests":["two workers cannot claim same task","lease expiry reassigns",
                   "old epoch rejected","six sources reconciled","durable reopen",
                   "replay skips committed tasks"],
          "not_tested":["GitHub cross-run snapshot transport","Google Drive persistence",
                        "real market scan","source-to-target SHA256","full migration"]}
  pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
  pathlib.Path(out).write_text(json.dumps(result,indent=2),encoding="utf-8")
  print(json.dumps(result))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",default="r9_test_evidence/result.json");smoke(p.parse_args().out)
