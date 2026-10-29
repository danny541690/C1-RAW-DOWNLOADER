import concurrent.futures,json,subprocess,tempfile,unittest
from pathlib import Path
from scripts.v093_source_git_store import GitCAS,StoreUnavailable
from scripts.v093_source_coordination import Coordinator

class GitStoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.remote=self.root/'remote.git';self.git('init','--bare',str(self.remote))
  self.a=self.repo('a');self.b=self.repo('b')
 def git(self,*args):return subprocess.run(['git',*args],check=True,capture_output=True)
 def repo(self,name):
  path=self.root/name;self.git('init',str(path));self.git('-C',str(path),'remote','add','origin',str(self.remote));return path
 def store(self,repo):return GitCAS(repo,'jarvis-source-preflight/local-test')
 def test_cold_runner_restores_saved_state_and_git_history(self):
  a=self.store(self.a);rev,value=a.read('TWSE');self.assertEqual((rev,value),(0,None))
  self.assertTrue(a.cas('TWSE',rev,dict(source='TWSE',counter=1)))
  first,v=self.store(self.b).read('TWSE');self.assertEqual(v['counter'],1)
  self.assertTrue(self.store(self.b).cas('TWSE',first,dict(source='TWSE',counter=2)))
  second,v=self.store(self.repo('cold')).read('TWSE');self.assertEqual(v['counter'],2)
  self.assertEqual(self.git('-C',str(self.b),'rev-parse',second+'^').stdout.decode().strip(),first)
 def test_stale_writer_never_overwrites_new_state(self):
  a=self.store(self.a);a.cas('TWSE',0,dict(source='TWSE',value=1));rev,_=a.read('TWSE');self.store(self.b).read('TWSE')
  self.assertTrue(a.cas('TWSE',rev,dict(source='TWSE',value=2)))
  self.assertFalse(self.store(self.b).cas('TWSE',rev,dict(source='TWSE',value='stale')))
  self.assertEqual(a.read('TWSE')[1]['value'],2)
 def test_identical_state_cannot_make_stale_cas_succeed(self):
  a=self.store(self.a);a.cas('TWSE',0,dict(source='TWSE',value=1));rev,value=a.read('TWSE')
  b=self.store(self.b);b.read('TWSE')
  self.assertTrue(a.cas('TWSE',rev,value))
  self.assertFalse(b.cas('TWSE',rev,value))
 def test_real_git_cas_admits_only_one_task_owner(self):
  a=self.store(self.a);c=Coordinator(a,'TWSE');c.add([dict(source='TWSE',key='task',slot='DESC',period='2026-10')])
  def claim(repo):return Coordinator(self.store(repo),'TWSE').claim('DESC',repo.name)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(claim,[self.a,self.b]))
  self.assertEqual(sum(x is not None for x in r),1)
 def test_auth_or_transport_error_cannot_be_mistaken_for_contention(self):
  self.git('-C',str(self.a),'remote','set-url','origin',str(self.root/'missing.git'))
  with self.assertRaises(StoreUnavailable):self.store(self.a).read('TWSE')
 def test_namespace_source_and_size_guards(self):
  with self.assertRaises(ValueError):GitCAS(self.a,'main')
  with self.assertRaises(ValueError):self.store(self.a).cas('TWSE',0,dict(source='MOPS'))
  with self.assertRaises(StoreUnavailable):GitCAS(self.a,'jarvis-source-preflight/small',max_bytes=1).cas('TWSE',0,dict(source='TWSE'))
  self.assertEqual(self.git('ls-remote','--heads',str(self.remote),'refs/heads/main').stdout,b'')
