"""Isolated prelaunch transaction prototype. SQLite is LOCAL to one runner.
Not a cross-GitHub-runner lock and never used to write production Google Drive.
"""
import sqlite3
def initialize(db):
    db.execute("CREATE TABLE IF NOT EXISTS leases (key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires INTEGER NOT NULL, fence INTEGER NOT NULL, digest TEXT)")
    db.commit()

def acquire(db,key,owner,now,ttl=300):
    if not key or not owner or ttl<=0:raise ValueError("BAD_LEASE_ARGUMENT")
    db.execute("BEGIN IMMEDIATE")
    try:
        old=db.execute("SELECT owner,expires,fence,digest FROM leases WHERE key=?",(key,)).fetchone()
        if old and old[1]>now:raise ValueError("LEASE_BUSY")
        if old and old[3] is not None:raise ValueError("ALREADY_COMMITTED")
        fence=(old[2]+1 if old else 1)
        db.execute("INSERT INTO leases(key,owner,expires,fence,digest) VALUES(?,?,?,?,NULL) ON CONFLICT(key) DO UPDATE SET owner=excluded.owner,expires=excluded.expires,fence=excluded.fence,digest=NULL",(key,owner,now+ttl,fence))
        db.commit()
        return fence
    except BaseException:
        db.rollback()
        raise

def commit(db,key,owner,fence,digest,now):
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError("BAD_DIGEST")
    db.execute("BEGIN IMMEDIATE")
    try:
        row=db.execute("SELECT owner,expires,fence,digest FROM leases WHERE key=?",(key,)).fetchone()
        if not row or row[0]!=owner or row[2]!=fence or row[1]<=now:raise ValueError("STALE_OR_EXPIRED_LEASE")
        if row[3] is not None:raise ValueError("ALREADY_COMMITTED")
        db.execute("UPDATE leases SET digest=? WHERE key=? AND owner=? AND fence=? AND digest IS NULL",(digest,key,owner,fence))
        db.commit()
    except BaseException:
        db.rollback()
        raise
