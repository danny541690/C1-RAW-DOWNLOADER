import copy,hashlib,unittest
from scripts.v093_acceptance_publish import publish
from scripts.v093_source_coordination import Coordinator
class Store:
 def __init__(self):self.s=None;self.rev=0
 def read(self,source):return self.rev,copy.deepcopy(self.s)
 def cas(self,source,rev,state):
  if rev!=self.rev:return False
  self.s=copy.deepcopy(state);self.rev+=1;return True
class Archive:
 def __init__(self):self.files={};self.fail=False;self.bad=False
 def save(self,raw,sha):
  self.files.setdefault(sha,raw)
  if self.fail:raise OSError('credential-like-error-must-not-be-recorded')
  return dict(file_id='same',sha256='0'*64 if self.bad else hashlib.sha256(self.files[sha]).hexdigest(),readback_verified=True)
class PublishTests(unittest.TestCase):
 def setUp(self):self.s=Store();self.c=Coordinator(self.s,'TWSE');self.a=Archive();self.r=dict(metadata=dict(job_status='failure'),files={'result.json':dict(text='failed case evidence')})
 def test_drive_interruption_preserves_git_and_retry_is_idempotent(self):
  self.a.fail=True
  with self.assertRaises(OSError):publish(self.c,self.r,self.a)
  self.assertEqual(self.s.s['publication_state'],'DRIVE_PENDING');self.assertEqual(self.s.s['tasks'],self.r['files']);self.assertEqual(self.s.s['publication_error'],'OSError')
  self.a.fail=False;publish(self.c,self.r,self.a);publish(self.c,self.r,self.a)
  self.assertEqual(len(self.a.files),1);self.assertEqual(self.s.s['record_metadata']['job_status'],'failure')
 def test_readback_mismatch_cannot_be_marked_published(self):
  self.a.bad=True
  with self.assertRaises(ValueError):publish(self.c,self.r,self.a)
  self.assertEqual(self.s.s['publication_state'],'DRIVE_PENDING')
 def test_changed_record_same_identity_never_overwrites_history(self):
  publish(self.c,self.r,self.a);before=copy.deepcopy(self.s.s);self.r['metadata']['job_status']='success'
  with self.assertRaisesRegex(ValueError,'CONTENT_CONFLICT'):publish(self.c,self.r,self.a)
  self.assertEqual(before,self.s.s)
