import copy,unittest
from scripts.v093_review_import import install
from scripts.v093_source_coordination import Coordinator
class Store:
 def __init__(self):self.state=None;self.rev=0
 def read(self,source):return self.rev,copy.deepcopy(self.state)
 def cas(self,source,rev,state):
  if rev!=self.rev:return False
  self.state=copy.deepcopy(state);self.rev+=1;return True
class ImportTests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.c=Coordinator(self.store,'TWSE')
  self.r=dict(tasks={'k':dict(source='TWSE',task_key='k',attempts=2,action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(period='2026-10',raw_reference='old',sha256='a'*64)])})
 def test_idempotence_preserves_later_progress(self):
  self.assertTrue(install(self.c,self.r,{'k':'DESC'},'g'))
  self.c.update(lambda s:s['tasks']['k'].update(attempts=3,status='CONTENT_BLOCKED'))
  self.assertFalse(install(self.c,self.r,{'k':'DESC'},'g'));t=self.store.state['tasks']['k']
  self.assertEqual(t['attempts'],3);self.assertEqual(t['status'],'CONTENT_BLOCKED');self.assertEqual(t['legacy_review'],self.r['tasks']['k'])
 def test_no_imported_record_is_downloadable_or_accepted(self):
  install(self.c,self.r,{'k':'DESC'},'g');self.assertIsNone(self.c.claim('DESC','runner'))
  t=self.store.state['tasks']['k'];self.assertFalse(t['full_acceptance']);self.assertFalse(t['download_authorized'])
 def test_existing_task_never_reset(self):
  self.c.add([dict(source='TWSE',key='k',slot='DESC',period='2026-10')]);before=copy.deepcopy(self.store.state)
  with self.assertRaisesRegex(ValueError,'IMPORT_EXISTING'):install(self.c,self.r,{'k':'DESC'},'g')
  self.assertEqual(before,self.store.state)
 def test_changed_generation_rejected(self):
  install(self.c,self.r,{'k':'DESC'},'g');self.r['tasks']['k']['attempts']=3
  with self.assertRaisesRegex(ValueError,'GENERATION_CONFLICT'):install(self.c,self.r,{'k':'DESC'},'g')
 def test_partition_and_cross_source_rejected_atomically(self):
  with self.assertRaises(ValueError):install(self.c,self.r,{},'g')
  self.r['tasks']['k']['source']='NDC'
  with self.assertRaises(ValueError):install(self.c,self.r,{'k':'DESC'},'g')
  self.assertIsNone(self.store.state)

 def test_conflicting_periods_quarantined_without_losing_versions(self):
  self.r['tasks']['k']['provenance'].append(dict(period='2026-09',attempts=1))
  install(self.c,self.r,{'k':'DESC'},'g')
  t=self.store.state['tasks']['k']
  self.assertEqual(t['status'],'CONTENT_BLOCKED');self.assertEqual(t['migration_issues'],['PERIOD_CONFLICT'])
  self.assertEqual(t['legacy_review'],self.r['tasks']['k']);self.assertIsNone(self.c.claim('DESC','runner'))
