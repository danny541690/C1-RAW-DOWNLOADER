import json,unittest,urllib.error
from scripts.v093_workflow_dispatch import WorkflowDispatch,DispatchUnavailable
class DispatchTests(unittest.TestCase):
 def test_explicit_post_carries_identity_and_ref(self):
  seen=[]
  class Response:
   status=204
   def __enter__(self):return self
   def __exit__(self,*args):pass
  def open_url(req,timeout):seen.append(req);return Response()
  d=WorkflowDispatch('owner/repo','jarvis-seven-continuation-test.yml','main','secret',{'phase':'verify'},open_url)
  d('a'*64);self.assertEqual(seen[0].method,'POST')
  self.assertEqual(json.loads(seen[0].data)['inputs']['continuation_id'],'a'*64)
 def test_uncertain_transport_is_sanitized_and_not_reported_success(self):
  def fail(*a,**kw):raise TimeoutError('secret response body')
  d=WorkflowDispatch('owner/repo','jarvis-seven-continuation-test.yml','main','secret',{},fail)
  with self.assertRaisesRegex(DispatchUnavailable,'TRANSPORT_UNCERTAIN') as caught:d('b'*64)
  self.assertNotIn('secret',str(caught.exception))
