import io,json,http.client,unittest,urllib.error
from unittest.mock import patch,Mock
from scripts import v093_five_stage_durable_gate as gate
from scripts.annual_actual_firstpass import Drive,retryable_drive_error
from googleapiclient.errors import HttpError
class Recovery(unittest.TestCase):
 def test_put_504_committed_verified(self):
  e=urllib.error.HTTPError('https://api.github.com/x',504,'timeout',{},None)
  p={'jobs':{'x':{'lease':{'owner':'a','fence':2}}}}
  with patch.object(gate.urllib.request,'urlopen',side_effect=e),patch.object(gate,'_read',return_value=('new',p)):
   self.assertTrue(gate._put('https://api.github.com/x','t','old',p,'m'))
 def test_put_504_not_committed_reloads(self):
  e=urllib.error.HTTPError('u',504,'timeout',{},None)
  with patch.object(gate.urllib.request,'urlopen',side_effect=e),patch.object(gate,'_read',return_value=('new',{'jobs':{}})):
   self.assertFalse(gate._put('https://api.github.com/x','t','old',{'jobs':{'x':{}}},'m'))
 def test_permission_denial_is_not_retryable(self):
  e=urllib.error.HTTPError('u',403,'denied',{},None)
  with patch.object(gate.urllib.request,'urlopen',side_effect=e):
   with self.assertRaises(urllib.error.HTTPError):gate._put('https://api.github.com/x','t','s',{},'m')
 def test_drive_rate_403_vs_permission(self):
  for reason,want in [('userRateLimitExceeded',True),('rateLimitExceeded',True),('insufficientPermissions',False),('dailyLimitExceeded',False)]:
   e=HttpError(Mock(status=403,reason='Forbidden'),json.dumps({'error':{'errors':[{'reason':reason}]}}).encode())
   self.assertEqual(retryable_drive_error(e),want)
 def test_incomplete_read_retries(self):
  q=Mock();q.execute.side_effect=[http.client.IncompleteRead(b'a',2),b'ok']
  with patch('scripts.annual_actual_firstpass.time.sleep'):
   self.assertEqual(Drive.call(lambda:q),b'ok')
  self.assertEqual(q.execute.call_count,2)
if __name__=='__main__':unittest.main()
