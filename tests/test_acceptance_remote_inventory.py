import json,tempfile,unittest
from pathlib import Path
from scripts.v093_acceptance_remote_inventory import collect,query
FOLDER='application/vnd.google-apps.folder'
def item(i,name,parent,mime=FOLDER):return dict(id=i,name=name,parents=[parent],mimeType=mime)
class RemoteInventoryTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
 def api(self,q,token):
  if "'root' in parents" in q:return {'files':[item('y','2026','root')]}
  if "'y' in parents" in q:return {'files':[item('s','TWSE','y')]}
  if "'s' in parents" in q:
   if token is None:return {'files':[item('m','2026-09','s')],'nextPageToken':'page2'}
   return {'files':[item('direct','top.zip','s','application/zip')]}
  return {'files':[item('raw','raw.zip','m','application/zip')]}
 def test_complete_pagination_and_recursive_scoped_folders(self):
  r=collect(self.api,self.p,root='root');self.assertTrue(r['enumeration_complete']);self.assertEqual(r['file_metadata_records'],2);self.assertFalse(r['raw_sha_readback_verified']);self.assertFalse(r['atomic_point_in_time_snapshot']);self.assertEqual(r['production_writes'],0)
 def test_budget_checkpoint_resumes_exact_page(self):
  first=collect(self.api,self.p,root='root',max_requests=3);self.assertFalse(first['enumeration_complete']);x=json.loads((self.p/'checkpoint.json').read_text());self.assertEqual(x['token'],'page2');r=collect(self.api,self.p,root='root',resume=self.p/'checkpoint.json');self.assertTrue(r['enumeration_complete']);self.assertEqual(r['requests_this_run'],2)
 def test_error_preserves_continuation_without_success(self):
  r=collect(lambda q,t:(_ for _ in ()).throw(ValueError('injected')),self.p,root='root');self.assertFalse(r['enumeration_complete']);self.assertEqual(r['phase'],'YEARS');self.assertTrue((self.p/'checkpoint.json').exists())
 def test_unrelated_parent_page_rejected(self):
  r=collect(lambda q,t:{'files':[item('x','2026','unrelated')]},self.p,root='root');self.assertFalse(r['enumeration_complete']);self.assertIn('INVENTORY_PARENT_SCOPE',r['error'])
 def test_year_canary_not_included(self):
  r=collect(lambda q,t:{'files':[item('x','CANARY_2026','root')]},self.p,root='root');self.assertFalse(r['enumeration_complete']);self.assertIn('INVENTORY_YEAR_SCOPE',r['error'])
 def test_resume_root_mismatch_rejected(self):
  collect(self.api,self.p,root='root',max_requests=1)
  with self.assertRaisesRegex(ValueError,'INVENTORY_RESUME_SCOPE'):collect(self.api,self.p,root='other',resume=self.p/'checkpoint.json')
 def test_query_rejects_parent_injection(self):
  with self.assertRaisesRegex(ValueError,'UNSAFE_DRIVE_PARENT'):query(["x' or true"])
