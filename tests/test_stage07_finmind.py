"""Actual FinMind adapter decisions with no provider calls or credentials."""
import ast,calendar,datetime as dt,hashlib,json,math,os,re,time,unittest,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
source=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_stage07_finmind.py').read_text())
key=lambda job:hashlib.sha256(json.dumps(job,sort_keys=True).encode()).hexdigest()
ns=dict(calendar=calendar,dt=dt,json=json,math=math,os=os,re=re,time=time,urllib=urllib,
        engine=SimpleNamespace(key=key),native=SimpleNamespace(sha=lambda b:hashlib.sha256(b).hexdigest()))
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,(ast.Assign,ast.FunctionDef,ast.ClassDef))],type_ignores=[]),'actual_finmind_adapter','exec'),ns)
actual_request=ns['request']
def payload(code,date='2000-01-04'):
    return json.dumps(dict(status=200,data=[dict(stock_id=code,date=date,open=10,max=12,min=9,close=11)])).encode()

class FinMindDownloadTests(unittest.TestCase):
    def worker(self):
        return SimpleNamespace(cursor={},state={'finmind_units':{},'attempt_ledger':{}},
            until=time.monotonic()+300,save_cursor=Mock(),save_state=Mock(),saved=0,processed=0)
    def test_full_candidate_directory_not_a_single_demo_stock(self):
        codes=ns['candidate_codes']([{'stock_id':'2330','type':'twse'},{'stock_id':'6488','type':'tpex'},
            {'stock_id':'9999','type':'emerging'}],[{'stock_id':'1234'}])
        self.assertEqual(codes,['1234','2330','6488'])
    def test_2000_january_plans_real_price_requests_for_every_candidate(self):
        jobs=list(ns['jobs']('2000-01',['1101','2330']))
        self.assertEqual([(j['dataset'],j['stock_id']) for j in jobs],
                         [('TaiwanStockPrice','1101'),('TaiwanStockPrice','2330')])
    def test_2000_quarter_includes_financial_history(self):
        self.assertIn('TaiwanStockFinancialStatements',[j['dataset'] for j in ns['jobs']('2000-03',['2330'])])
    def test_wrong_stock_or_period_never_count_as_saved(self):
        job=list(ns['jobs']('2000-01',['2330']))[0]
        for raw in (payload('1101'),payload('2330','2026-01-04')):
            with self.assertRaises(ValueError):ns['validate'](raw,job)
    def test_empty_response_is_not_data_coverage(self):
        job=list(ns['jobs']('2000-01',['2330']))[0]
        self.assertIsNone(ns['validate'](b'{"status":200,"data":[]}',job))
    def test_supplement_actually_requests_and_persists_each_stock(self):
        worker=self.worker()
        def save(job,raw,receipt,bucket):
            worker.state[bucket][key(job)]=receipt;worker.saved+=1
        worker.record_payload=save
        with patch.dict(ns,universe=Mock(return_value=['1101','2330']),
                        request=Mock(side_effect=[payload('1101'),payload('2330')])):
            self.assertTrue(ns['supplement'](worker,'2000-01'))
        self.assertEqual(worker.saved,2)
        self.assertEqual(worker.state['finmind_saved_units'],2)
        self.assertTrue(all(r['status']=='SAVED_BASIC_VERIFIED' for r in worker.state['finmind_units'].values()))
        self.assertFalse(worker.state['historical_universe_complete'])
    def test_provider_pause_does_not_exhaust_download_attempts(self):
        worker=self.worker()
        with patch.dict(ns,universe=Mock(return_value=['2330']),
                        request=Mock(side_effect=ns['ProviderPause']('quota'))):
            self.assertFalse(ns['supplement'](worker,'2000-01'))
        self.assertEqual(list(worker.state['attempt_ledger']['finmind_units'].values()),[0])
    def test_local_hourly_budget_blocks_network_before_send(self):
        worker=self.worker();worker.cursor['finmind_requests_utc']=[time.time()]*480
        with patch.dict(os.environ,{'FINMIND_TOKEN':'test'}),patch.object(urllib.request,'urlopen') as fetch:
            with self.assertRaises(ns['ProviderPause']):actual_request(worker,{'dataset':'TaiwanStockInfo'})
        fetch.assert_not_called()
    def test_saved_stock_is_not_downloaded_again(self):
        worker=self.worker();job=list(ns['jobs']('2000-01',['2330']))[0]
        worker.state['finmind_units'][key(job)]=dict(job,status='SAVED_BASIC_VERIFIED')
        with patch.dict(ns,universe=Mock(return_value=['2330']),request=Mock()) as ignored:
            fetch=ns['request'];self.assertTrue(ns['supplement'](worker,'2000-01'));fetch.assert_not_called()

if __name__=='__main__':unittest.main()
