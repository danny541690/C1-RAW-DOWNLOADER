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
            execute_month(2024,2,[{"key":"k","source":"MOPS"}],fetch,lambda u,d:True,path)
            self.assertEqual(count[0],1)
    def test_month_independence(self):
        with tempfile.TemporaryDirectory() as path:
            u=[{"key":"a","source":"FinMind"}]
            one=execute_month(2024,1,u,lambda u:{"ok":False,"error":"HTTP_403"},lambda u,d:True,path)
            two=execute_month(2024,2,u,lambda u:{"ok":True,"data":b"ok"},lambda u,d:True,path)
            self.assertEqual(one["missing"],1)
            self.assertEqual(two["saved_basic_valid"],1)

    def test_interruption_keeps_prior_saved_unit(self):
        calls={}
        units=[{"key":"first","source":"TWSE"},{"key":"second","source":"TPEx"}]
        def fetch(u):
            calls[u["key"]]=calls.get(u["key"],0)+1
            return {"ok":True,"data":b"payload"}
        def interrupted_persist(u,d):
            if u["key"]=="second":
                raise KeyboardInterrupt("simulated runner cancellation")
            return True
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(KeyboardInterrupt):
                execute_month(2024,3,units,fetch,interrupted_persist,path)
            resumed=execute_month(2024,3,units,fetch,lambda u,d:True,path)
            self.assertEqual(resumed["saved_basic_valid"],2)
            self.assertEqual(calls["first"],1)
            self.assertEqual(calls["second"],2)

    def test_persist_failure_never_counts_as_saved(self):
        with tempfile.TemporaryDirectory() as path:
            calls=[0]
            def fetch(u):
                calls[0]+=1
                return {"ok":True,"data":b"real-bytes-not-saved"}
            r=execute_month(2024,4,[{"key":"missing-upload","source":"TWSE"}],
                            fetch,lambda u,d:False,path)
            self.assertEqual(calls[0],4)
            self.assertEqual(r["saved_basic_valid"],0)
            self.assertEqual(r["missing"],1)
            import json
            from pathlib import Path
            ledger=json.loads((Path(path)/"2024"/"04"/"checkpoint.json").read_text())
            self.assertEqual(ledger["missing-upload"]["status"],"FAILED_RETRY_LIMIT")
            self.assertEqual(ledger["missing-upload"]["last_error"],"NOT_PERSISTED")
            execute_month(2024,4,[{"key":"missing-upload","source":"TWSE"}],
                          fetch,lambda u,d:True,path)
            self.assertEqual(calls[0],4)

    def test_retryable_failure_then_success(self):
        with tempfile.TemporaryDirectory() as path:
            calls=[0]
            def fetch(u):
                calls[0]+=1
                if calls[0] < 3:
                    return {"ok":False,"error":"HTTP_503"}
                return {"ok":True,"data":b"payload"}
            r=execute_month(2024,5,[{"key":"recovered","source":"TPEx"}],
                            fetch,lambda u,d:True,path)
            self.assertEqual(calls[0],3)
            self.assertEqual(r["saved_basic_valid"],1)

    def test_interrupted_request_does_not_reset_retry_budget(self):
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as path:
            calls=[0]
            def fetch(u):
                calls[0]+=1
                if calls[0] <= 3:
                    raise KeyboardInterrupt("simulated runner killed during HTTP request")
                return {"ok":True,"data":b"payload"}
            unit=[{"key":"interrupted","source":"TWSE"}]
            for n in range(3):
                with self.assertRaises(KeyboardInterrupt):
                    execute_month(2024,6,unit,fetch,lambda u,d:True,path)
                saved=json.loads((Path(path)/"2024"/"06"/"checkpoint.json").read_text())
                self.assertEqual(saved["interrupted"]["attempts"],n+1)
            result=execute_month(2024,6,unit,fetch,lambda u,d:True,path)
            self.assertEqual(calls[0],4)
            self.assertEqual(result["saved_basic_valid"],1)
            execute_month(2024,6,unit,fetch,lambda u,d:True,path)
            self.assertEqual(calls[0],4)

    def test_four_killed_requests_are_not_retried_on_next_run(self):
        with tempfile.TemporaryDirectory() as path:
            calls=[0]
            def fetch(u):
                calls[0]+=1
                raise KeyboardInterrupt("simulated job termination")
            unit=[{"key":"maxed","source":"TPEx"}]
            for _ in range(4):
                with self.assertRaises(KeyboardInterrupt):
                    execute_month(2024,7,unit,fetch,lambda u,d:True,path)
            result=execute_month(2024,7,unit,fetch,lambda u,d:True,path)
            self.assertEqual(calls[0],4)
            self.assertEqual(result["missing"],1)

if __name__=="__main__":
    unittest.main()
