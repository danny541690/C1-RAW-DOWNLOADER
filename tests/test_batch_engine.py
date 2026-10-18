import tempfile
import unittest
from scripts.batch_engine import execute_month

class BatchEngineTest(unittest.TestCase):
    def test_retry_three_then_continue_and_resume(self):
        calls={}
        def fetch(u):
            k=u["key"]; calls[k]=calls.get(k,0)+1
            if k=="bad": return {"ok":False,"error":"HTTP_503"}
            return {"ok":True,"data":b"ok"}
        units=[{"key":"bad","source":"TWSE"},{"key":"good","source":"TPEx"}]
        with tempfile.TemporaryDirectory() as path:
            a=execute_month(2024,1,units,fetch,lambda u,d:True,path)
            self.assertEqual((calls["bad"],calls["good"]), (4,1))
            self.assertEqual((a["saved_basic_valid"],a["missing"]),(1,1))
            b=execute_month(2024,1,units,fetch,lambda u,d:True,path)
            self.assertEqual((calls["bad"],calls["good"]), (4,1))
            self.assertEqual(b["status"],"FINISHED_WITH_GAPS")
    def test_permanent_error_hold(self):
        with tempfile.TemporaryDirectory() as path:
            count=[0]
            def fetch(u):
                count[0]+=1
                return {"ok":False,"error":"HTTP_403"}
            r=execute_month(2024,2,[{"key":"k","source":"MOPS"}],fetch,lambda u,d:True,path)
            self.assertEqual(count[0],1)
            self.assertEqual(r["missing"],1)
    def test_month_independence(self):
        with tempfile.TemporaryDirectory() as path:
            u=[{"key":"a","source":"FinMind"}]
            one=execute_month(2024,1,u,lambda u:{"ok":False,"error":"HTTP_403"},lambda u,d:True,path)
            two=execute_month(2024,2,u,lambda u:{"ok":True,"data":b"ok"},lambda u,d:True,path)
            self.assertEqual(one["missing"],1)
            self.assertEqual(two["saved_basic_valid"],1)

if __name__=="__main__":
    unittest.main()
