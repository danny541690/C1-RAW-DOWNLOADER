import copy,json,unittest
from scripts.v093_source_state_pages import pack,unpack
class PageTests(unittest.TestCase):
 def test_multiple_pages_roundtrip_and_partial_page_update_preserves_others(self):
  state=dict(source='TWSE',fence=9,tasks={str(i):dict(status='READY_CHECK',attempts=3,value='x'*100) for i in range(20)})
  files=pack(state,page_bytes=1200);self.assertGreater(len(files),2)
  self.assertEqual(unpack(files['state.json'],files.__getitem__,page_bytes=1200),state)
  newer=copy.deepcopy(state);newer['tasks']['0']['status']='VERIFIED'
  updated=pack(newer,page_bytes=1200)
  self.assertTrue(any(files[n]==updated[n] for n in files if n!='state.json' and n in updated))
 def test_tampering_missing_page_and_oversize_fail_closed(self):
  state=dict(source='TWSE',tasks={'a':dict(status='READY')});files=pack(state,1024)
  with self.assertRaisesRegex(ValueError,'HASH'):unpack(files['state.json'],lambda _:b'{}',1024)
  with self.assertRaises(KeyError):unpack(files['state.json'],{}.__getitem__,1024)
  with self.assertRaisesRegex(ValueError,'TOTAL'):pack(state,1024,max_bytes=2)
  with self.assertRaisesRegex(ValueError,'SINGLE_TASK'):pack(dict(tasks={'a':'x'*2000}),1024)
