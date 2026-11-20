#!/usr/bin/env python3
"""JARVIS v0.98 R8 seven-ledger dry-run contract.
No Google Drive reads/writes. No real data downloads or migrations.
Six workers produce append-only independent receipts. Single reconciler owns
the SQLite Master commit; task_key uniqueness and attempt fencing enforced.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
import sys

SOURCES = ("TWSE", "TPEx", "MOPS", "NDC", "TDCC", "TAIFEX")
def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")
def dump(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
def key(src, dataset, period, op):
    return hashlib.sha256(f"{src}|{dataset}|{period}|{op}".encode()).hexdigest()
def task(src):
    return {"source": src, "dataset": "SYNTHETIC_CONTRACT_TEST",
            "period": "2000-01", "op": "INVENTORY_DRY_RUN",
            "task_key": key(src, "SYNTHETIC_CONTRACT_TEST", "2000-01", "INVENTORY_DRY_RUN")}
def worker(src, out, run_id):
    if src not in SOURCES:
        raise ValueError("Unknown source")
    t = task(src)
    started = now()
    attempt_id = f"{run_id}:{src}:1"
    events = [
        {"event": "DISPATCH_RECEIVED", "at": started, "attempt_id": attempt_id, **t},
        {"event": "EXECUTION_STARTED", "at": now(), "attempt_id": attempt_id, **t},
        {"event": "EXECUTION_FINISHED", "at": now(), "attempt_id": attempt_id, **t,
         "status": "PASS_DRY_RUN", "evidence": {"files_written": 0, "real_drive_access": False}}
    ]
    path = pathlib.Path(out)
    path.mkdir(parents=True, exist_ok=True)
    for event in events:
        dump(path / f"{src}.jsonl", event)
    print(json.dumps({"source": src, "attempt": attempt_id, "status": "PASS_DRY_RUN"}))
def initialize(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks(
        task_key TEXT PRIMARY KEY, source TEXT NOT NULL, dataset TEXT NOT NULL,
        period TEXT NOT NULL, operation TEXT NOT NULL,
        status TEXT NOT NULL, accepted_attempt TEXT, committed_at TEXT);
    CREATE TABLE IF NOT EXISTS attempts(
        attempt_id TEXT PRIMARY KEY, task_key TEXT NOT NULL,
        started_at TEXT, finished_at TEXT, status TEXT,
        FOREIGN KEY(task_key) REFERENCES tasks(task_key));
    CREATE TABLE IF NOT EXISTS events(
        seq INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT NOT NULL,
        event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, payload TEXT NOT NULL,
        UNIQUE(attempt_id,event_type));
    """)
def reconcile(inputs, db, report):
    paths = sorted(pathlib.Path(inputs).glob("*.jsonl"))
    if len(paths) != 6 or {p.stem for p in paths} != set(SOURCES):
        raise RuntimeError("Expected exactly 6 source account receipts")
    conn = sqlite3.connect(db)
    initialize(conn)
    commits = []
    for path in paths:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != 3:
            raise RuntimeError(f"{path.name}: expected three receipt events")
        ev = [r["event"] for r in rows]
        if ev != ["DISPATCH_RECEIVED", "EXECUTION_STARTED", "EXECUTION_FINISHED"]:
            raise RuntimeError("Invalid lifecycle " + path.name)
        base = rows[0]
        for row in rows:
            for k in ["task_key", "source", "dataset", "period", "op", "attempt_id"]:
                if row[k] != base[k]:
                    raise RuntimeError("Cross-event identity mismatch")
        if base["source"] != path.stem:
            raise RuntimeError("Cross-source account mismatch")
        expected = key(base["source"], base["dataset"], base["period"], base["op"])
        if base["task_key"] != expected:
            raise RuntimeError("Tampered task key")
        finished = rows[-1]
        if finished["status"] != "PASS_DRY_RUN" or finished["evidence"]["real_drive_access"]:
            raise RuntimeError("Unapproved real data access")
        with conn:
            conn.execute("INSERT OR IGNORE INTO tasks(task_key,source,dataset,period,operation,status) VALUES(?,?,?,?,?,?)",
                         (expected, base["source"], base["dataset"], base["period"], base["op"], "PENDING"))
            t = conn.execute("SELECT status,accepted_attempt FROM tasks WHERE task_key=?", (expected,)).fetchone()
            if t[0] == "COMMITTED":
                commits.append({"source": base["source"], "status": "SKIP_ALREADY_COMMITTED"})
                continue
            conn.execute("INSERT OR IGNORE INTO attempts(attempt_id,task_key,started_at,finished_at,status) VALUES(?,?,?,?,?)",
                         (base["attempt_id"], expected, rows[1]["at"], finished["at"], finished["status"]))
            for r in rows:
                conn.execute("INSERT OR IGNORE INTO events(attempt_id,event_type,occurred_at,payload) VALUES(?,?,?,?)",
                             (r["attempt_id"], r["event"], r["at"], json.dumps(r, ensure_ascii=False)))
            conn.execute("UPDATE tasks SET status='COMMITTED',accepted_attempt=?,committed_at=? WHERE task_key=? AND status='PENDING'",
                         (base["attempt_id"], now(), expected))
            commits.append({"source": base["source"], "status": "COMMITTED_DRY_RUN"})
    summary = {
        "at": now(), "mode": "SYNTHETIC_ONLY",
        "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        "committed": conn.execute("SELECT COUNT(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0],
        "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "attempts": conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
        "sources": commits, "real_market_data_processed": False
    }
    conn.close()
    pathlib.Path(report).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(report).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["tasks"] != 6 or summary["committed"] != 6 or summary["events"] != 18:
        raise RuntimeError("Seven-ledger reconciliation failed")
def selftest(out):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        folder = pathlib.Path(d)
        receipts = folder / "accounts"
        for src in SOURCES:
            worker(src, receipts, "TEST-RUN")
        db = folder / "master.sqlite"
        summary = folder / "summary.json"
        reconcile(receipts, db, summary)
        reconcile(receipts, db, summary)
        state = json.loads(summary.read_text())
        assert state["tasks"] == 6 and state["events"] == 18
        assert all(x["status"] == "SKIP_ALREADY_COMMITTED" for x in state["sources"])
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_text(json.dumps({"status": "PASS", "tests": [
            "six independent accounts", "all lifecycle timestamps",
            "stable task identity", "single writer", "idempotent replay",
            "cross-account reconciliation"], "synthetic_only": True}, indent=2))
def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("worker", "reconcile", "selftest"))
    p.add_argument("--source", choices=SOURCES)
    p.add_argument("--out", default="r8_out")
    p.add_argument("--run-id", default="R8-LOCAL")
    p.add_argument("--inputs")
    p.add_argument("--db", default="r8_master.sqlite")
    p.add_argument("--report", default="r8_summary.json")
    a = p.parse_args()
    if a.mode == "worker":
        if not a.source: p.error("--source required")
        worker(a.source, a.out, a.run_id)
    elif a.mode == "reconcile":
        reconcile(a.inputs or a.out, a.db, a.report)
    else:
        selftest(a.report)
if __name__ == "__main__":
    main()
