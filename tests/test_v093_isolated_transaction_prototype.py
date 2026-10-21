import os,sqlite3,tempfile,threading,unittest
from scripts.v093_isolated_transaction_prototype import initialize,acquire,commit
KEY='2026-10:ohlc:RAW'
SHA='a'*64

class TransactionPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.temp.name,'lease.db')
        with sqlite3.connect(self.path,timeout=10) as db:initialize(db)
    def tearDown(self):self.temp.cleanup()
    def connection(self):return sqlite3.connect(self.path,timeout=10)
    def test_two_simultaneous_writers_exactly_one_wins(self):
        barrier=threading.Barrier(2);results=[]
        def worker(owner):
            with self.connection() as db:
                barrier.wait(timeout=5)
                try:results.append(('ok',owner,acquire(db,KEY,owner,100,ttl=20)))
                except ValueError as e:results.append(('blocked',owner,str(e)))
        ts=[threading.Thread(target=worker,args=(str(i),)) for i in range(2)]
        for t in ts:t.start()
        for t in ts:t.join(timeout=10)
        self.assertFalse(any(t.is_alive() for t in ts))
        self.assertEqual(sum(r[0]=='ok' for r in results),1,results)
        self.assertEqual(sum(r[0]=='blocked' for r in results),1,results)
    def test_expired_lease_reclaim_and_fence(self):
        with self.connection() as db:
            a=acquire(db,KEY,'old',100,ttl=10)
            b=acquire(db,KEY,'new',110,ttl=10)
            self.assertEqual((a,b),(1,2))
            with self.assertRaisesRegex(ValueError,'STALE_OR_EXPIRED_LEASE'):commit(db,KEY,'old',a,SHA,111)
            commit(db,KEY,'new',b,SHA,111)
    def test_exactly_one_commit(self):
        with self.connection() as db:
            token=acquire(db,KEY,'a',100)
            commit(db,KEY,'a',token,SHA,101)
            with self.assertRaisesRegex(ValueError,'ALREADY_COMMITTED'):commit(db,KEY,'a',token,SHA,102)
            with self.assertRaisesRegex(ValueError,'ALREADY_COMMITTED'):acquire(db,KEY,'b',999)
    def test_expired_owner_cannot_commit(self):
        with self.connection() as db:
            token=acquire(db,KEY,'a',100,ttl=5)
            with self.assertRaisesRegex(ValueError,'STALE_OR_EXPIRED_LEASE'):commit(db,KEY,'a',token,SHA,105)
    def test_other_key_independent(self):
        with self.connection() as db:
            self.assertEqual(acquire(db,KEY,'a',100),1)
            self.assertEqual(acquire(db,'2026-09:ohlc:RAW','b',100),1)
    def test_digest_is_required(self):
        with self.connection() as db:
            token=acquire(db,KEY,'a',100)
            with self.assertRaisesRegex(ValueError,'BAD_DIGEST'):commit(db,KEY,'a',token,'not_sha',101)

if __name__=='__main__':unittest.main()
