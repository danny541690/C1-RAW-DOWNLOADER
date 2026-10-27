import unittest,json,pathlib,time,hashlib,socket,sys
R=pathlib.Path(__file__).parent;out=R/'results';out.mkdir(exist_ok=True)
# Offline contract tests: deny any unexpected network connection; test doubles still operate.
def denied(*a,**k):raise RuntimeError('LIVE_NETWORK_DISABLED_FOR_TESTS')
socket.socket.connect=denied;socket.socket.connect_ex=denied
class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.items=[]
 def addSuccess(self,t):super().addSuccess(t);self.items.append({'test':t.id(),'status':'PASS'})
 def addFailure(self,t,e):super().addFailure(t,e);self.items.append({'test':t.id(),'status':'FAIL','detail':self._exc_info_to_string(e,t)})
 def addError(self,t,e):super().addError(t,e);self.items.append({'test':t.id(),'status':'ERROR','detail':self._exc_info_to_string(e,t)})
 def addSkip(self,t,why):super().addSkip(t,why);self.items.append({'test':t.id(),'status':'SKIP','detail':why})
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'))
with open(out/'test.log','w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2,resultclass=Result).run(suite)
x={'version':'JARVIS_FULL_REPOSITORY_RELEASE_BATCH_20261027_V6','base_commit':'089e63211f65a13fca583432bfc3d5a14f28f003','tested_version':'isolated candidate; source hashes in manifest','elapsed_seconds':round(time.monotonic()-start,3),'counts':{'run':r.testsRun,'pass':sum(i['status']=='PASS' for i in r.items),'fail':len(r.failures),'error':len(r.errors),'skip':len(r.skipped)},'live_network_disabled':True,'market_downloads':0,'production_changes':0,'database_completeness':'UNKNOWN','tests':r.items}
(out/'results.json').write_text(json.dumps(x,ensure_ascii=False,indent=2));print(json.dumps(x['counts']));print('elapsed',x['elapsed_seconds']);sys.exit(not r.wasSuccessful())
