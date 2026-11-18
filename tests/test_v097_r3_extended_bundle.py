"""Extended R3 bundled stress tests. Pure simulated workloads; NO Drive/GitHub mutation."""
import unittest
from dataclasses import dataclass
from hashlib import sha256
from scripts.v097_r3_gate_core import (
    Template, evidence_key, check_migration, template_for, match_fields,
    reusable, next_gate, disposition, reconcile, SOURCES, GATES
)

SHA = sha256(b"source").hexdigest()

@dataclass
class Lease:
    owner: str
    version: int
    expires: int

class InMemorySourceQueue:
    """Contract simulation, not a production transactional queue."""
    def __init__(self, source, count):
        self.source=source
        self.ids=[f"{source}:{i}" for i in range(count)]
        self.lease={}
        self.final={}
        self.retries={}
    def claim(self, key, owner, now, ttl):
        if key not in self.ids or key in self.final:
            return None
        current=self.lease.get(key)
        if current is not None and current.expires > now:
            return None
        version=(current.version+1) if current else 1
        result=Lease(owner,version,now+ttl)
        self.lease[key]=result
        return result
    def commit(self,key,lease,now,state):
        current=self.lease.get(key)
        if key in self.final or current != lease or current.expires <= now:
            return False
        self.final[key]=state
        return True
    def fail_transient(self,key,lease,now):
        current=self.lease.get(key)
        if current != lease or current.expires <= now:
            return False
        self.retries[key]=self.retries.get(key,0)+1
        if self.retries[key]>=3:
            self.final[key]="HOLD"
        self.lease.pop(key,None)
        return True

class R3ExtendedSuite(unittest.TestCase):
    def test_70_gate_cases_mixed(self):
        cases=[]
        for i in range(70):
            mode=i%7
            result=check_migration(source_sha=SHA,destination_sha=(SHA if mode!=0 else sha256(str(i).encode()).hexdigest()))
            t=Template(SOURCES[i//10],"quotes","era1","2000-01-01",None,
                       frozenset({"date","volume"}),frozenset({"memo"}),
                       {"交易股數":"volume"},"approved-reference",mode not in (2,5))
            names=["date","交易股數"] if mode not in (3,4) else ["date","count"]
            format_result=match_fields(t,names)
            cases.append((result["status"],format_result["status"]))
        self.assertEqual(len(cases),70)
        self.assertEqual(sum(g=="PASS" and f=="PASS" for g,f in cases),20)
        self.assertEqual(sum(g=="HOLD" or f=="HOLD" for g,f in cases),50)
    def test_700_source_queue_races_and_recovery(self):
        pools={src:InMemorySourceQueue(src,100) for src in SOURCES}
        for pool in pools.values():
            for i,key in enumerate(pool.ids):
                lease=pool.claim(key,"workerA",now=0,ttl=4)
                self.assertIsNotNone(lease)
                self.assertIsNone(pool.claim(key,"workerB",now=1,ttl=4))
                if i%10==0:
                    fresh=pool.claim(key,"workerB",now=5,ttl=4)
                    self.assertFalse(pool.commit(key,lease,6,"SILVER_READY"))
                    self.assertTrue(pool.commit(key,fresh,6,"SILVER_READY"))
                elif i%10==1:
                    self.assertTrue(pool.fail_transient(key,lease,1))
                    second=pool.claim(key,"workerB",2,4)
                    self.assertTrue(pool.fail_transient(key,second,3))
                    third=pool.claim(key,"workerA",4,4)
                    self.assertTrue(pool.fail_transient(key,third,5))
                    self.assertEqual(pool.final[key],"HOLD")
                else:
                    self.assertTrue(pool.commit(key,lease,1,"SILVER_READY"))
                self.assertFalse(pool.commit(key,lease,2,"SILVER_READY"))
        states=[{"record_id":key,"source":src,"status":status}
                for src,pool in pools.items() for key,status in pool.final.items()]
        self.assertEqual(len(states),700)
        self.assertEqual(reconcile(states)["states"]["HOLD"],70)
        self.assertEqual(reconcile(states)["states"]["SILVER_READY"],630)
    def test_1000_handover_replay_and_no_false_ready(self):
        rows=[]
        for i in range(1000):
            src=SOURCES[i%7]
            if i%10==0: status="HOLD"
            elif i%17==0: status="EXCLUDED"
            else: status="SILVER_READY"
            rows.append({"record_id":f"cohort-{i}","source":src,"status":status})
        count1=reconcile(rows)
        count2=reconcile([dict(r) for r in rows])
        self.assertEqual(count1,count2)
        self.assertEqual(count1["count"],1000)
        self.assertEqual(sum(count1["states"].values()),1000)
        self.assertFalse(count1["complete"])  # only 1000 of frozen 74750
        self.assertEqual(disposition({g:"PASS" for g in GATES},durable_release=False),"PENDING")
        self.assertEqual(disposition({"G1":"PASS","G2":"NOT_APPLICABLE","G3":"PASS","G4":"PASS","G5":"PASS"},durable_release=True),"PENDING")
        with self.assertRaises(ValueError):
            reconcile(rows+[rows[0]])
    def test_era_edges_evidence_keys_and_field_safety(self):
        first=Template("TWSE","d","first","2000-01-01","2010-12-31",
                       frozenset({"date","volume"}),aliases={"交易股數":"volume"},
                       official_evidence="official",evidence_verified=True)
        second=Template("TWSE","d","second","2011-01-01",None,
                        frozenset({"date","volume"}),official_evidence="official",evidence_verified=True)
        self.assertEqual(template_for([first,second],"TWSE","d","2010-12-31").template_id,"first")
        self.assertEqual(template_for([first,second],"TWSE","d","2011-01-01").template_id,"second")
        self.assertEqual(match_fields(first,["date","volume","交易股數"])["reason"],"DUPLICATE_SEMANTIC_FIELDS")
        self.assertEqual(check_migration(source_sha="x"*64,destination_sha="x"*64)["status"],"HOLD")
        key1=evidence_key("rec",SHA,"G2","r3",template_version="a")
        key2=evidence_key("rec",SHA,"G2","r3",template_version="b")
        self.assertNotEqual(key1,key2)
        self.assertFalse(reusable({"evidence_key":key1,"status":"PASS","durably_committed":True},key2))
        g1=evidence_key("rec",SHA,"G1","r3",template_version="a")
        self.assertEqual(g1,evidence_key("rec",SHA,"G1","r3",template_version="b"))

if __name__=="__main__":
    unittest.main()
