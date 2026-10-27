import unittest,json,pathlib,time,hashlib,socket,sys,subprocess
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
try: checkout_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
except (OSError,subprocess.CalledProcessError): checkout_commit=None
input_paths=sorted({p for folder in ('scripts','tests','config','.github/workflows') for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.yml','.yaml')} | {R/'requirements-qa.lock',R/'run_release_batch.py'})
input_manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths if p.exists()}
input_signature=hashlib.sha256(json.dumps(input_manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
start=time.monotonic();suite=unittest.defaultTestLoader.discover(str(R/'tests'))
with open(out/'test.log','w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2,resultclass=Result).run(suite)
x={'version':'JARVIS_POSTLAUNCH_FULL_SUITE_20261027_V7','base_commit':checkout_commit,'execution_input_sha256':input_signature,'tested_version':'isolated candidate; source hashes in manifest','elapsed_seconds':round(time.monotonic()-start,3),'counts':{'run':r.testsRun,'pass':sum(i['status']=='PASS' for i in r.items),'fail':len(r.failures),'error':len(r.errors),'skip':len(r.skipped)},'live_network_disabled':True,'market_downloads':0,'production_changes':0,'database_completeness':'UNKNOWN','tests':r.items}
(out/'results.json').write_text(json.dumps(x,ensure_ascii=False,indent=2));print(json.dumps(x['counts']));print('elapsed',x['elapsed_seconds']);sys.exit(not r.wasSuccessful())
