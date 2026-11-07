"""R9: two-process GitHub runner locking + lost ACK recovery. SYNTHETIC ONLY.
This verifies same-runner advisory lock discipline, NOT distributed Drive/GitHub CAS.
"""
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

def candidate(root, name, data):
    path = Path(root) / "candidates" / (name + ".bin")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": str(path.relative_to(root)), "sha": hashlib.sha256(data).hexdigest(),
            "partition": "TWSE/margin/year=2026", "source_hash": "a"*64}

def read_pointer(root):
    p = Path(root) / "release.json"
    return json.loads(p.read_text()) if p.exists() else {"generation": 0, "partitions": {}}

def try_publish(root, c, expected, fence, wait=0.0):
    root = Path(root)
    with (root / "publisher.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            p = read_pointer(root)
            if p["generation"] != expected: return "STALE_GENERATION"
            if fence != "ACTIVE": return "STALE_FENCE"
            data = (root / c["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != c["sha"]: return "BAD_SHA"
            if wait: time.sleep(wait)
            new = {"generation": expected+1, "partitions": dict(p["partitions"])}
            new["partitions"][c["partition"]] = c
            temp = root / (".release-" + str(os.getpid()) + ".tmp")
            temp.write_text(json.dumps(new,sort_keys=True))
            os.replace(temp, root / "release.json")
            return "PUBLISHED"
        finally: fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def reconcile_ack(root, c):
    p = read_pointer(root)
    old = p["partitions"].get(c["partition"])
    return "ALREADY_PUBLISHED" if old and old["sha"] == c["sha"] else "UNPUBLISHED"

class Tests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = self.t.name
    def tearDown(self): self.t.cleanup()
    def test_01_two_real_processes_only_one_publishes(self):
        a = candidate(self.root, "worker-a", b"date,buy\n2026-10-22,10\n")
        b = candidate(self.root, "worker-b", b"date,buy\n2026-10-22,20\n")
        commands = [[sys.executable,__file__,"worker",self.root,json.dumps(c),"0","ACTIVE"] for c in (a,b)]
        children = [subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for cmd in commands]
        outcomes = []
        for child in children:
            stdout,stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode,0,stderr)
            outcomes.append(stdout.strip())
        self.assertCountEqual(outcomes,["PUBLISHED","STALE_GENERATION"])
        self.assertEqual(read_pointer(self.root)["generation"],1)
    def test_02_lost_ack_recovery_avoids_repulish(self):
        a = candidate(self.root,"a",b"alpha")
        self.assertEqual(try_publish(self.root,a,0,"ACTIVE"),"PUBLISHED")
        self.assertEqual(reconcile_ack(self.root,a),"ALREADY_PUBLISHED")
        self.assertEqual(read_pointer(self.root)["generation"],1)
    def test_03_crash_before_publish_no_pointer(self):
        candidate(self.root,"a",b"alpha")
        self.assertEqual(read_pointer(self.root)["generation"],0)
    def test_04_stale_fence_blocks(self):
        a=candidate(self.root,"a",b"alpha")
        self.assertEqual(try_publish(self.root,a,0,"EXPIRED"),"STALE_FENCE")
    def test_05_mismatched_bytes_block(self):
        a=candidate(self.root,"a",b"alpha")
        (Path(self.root)/a["path"]).write_bytes(b"tampered")
        self.assertEqual(try_publish(self.root,a,0,"ACTIVE"),"BAD_SHA")
    def test_06_old_version_retained_after_switch(self):
        a=candidate(self.root,"a",b"alpha")
        b=candidate(self.root,"b",b"beta")
        self.assertEqual(try_publish(self.root,a,0,"ACTIVE"),"PUBLISHED")
        self.assertEqual(try_publish(self.root,b,1,"ACTIVE"),"PUBLISHED")
        self.assertEqual((Path(self.root)/a["path"]).read_bytes(),b"alpha")
        self.assertEqual(reconcile_ack(self.root,b),"ALREADY_PUBLISHED")
    def test_07_no_false_ack_when_different_payload(self):
        a=candidate(self.root,"a",b"alpha")
        b=candidate(self.root,"b",b"beta")
        try_publish(self.root,a,0,"ACTIVE")
        self.assertEqual(reconcile_ack(self.root,b),"UNPUBLISHED")
    def test_08_reject_stale_generation(self):
        a=candidate(self.root,"a",b"alpha")
        try_publish(self.root,a,0,"ACTIVE")
        self.assertEqual(try_publish(self.root,a,0,"ACTIVE"),"STALE_GENERATION")

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="worker":
        print(try_publish(sys.argv[2],json.loads(sys.argv[3]),int(sys.argv[4]),sys.argv[5],0.03))
    else: unittest.main(verbosity=2)
