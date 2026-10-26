import io,json,unittest,urllib.error
from unittest.mock import patch,Mock
from scripts import v093_github_budget as b
from scripts.v093_repair_coordination import lane_months
class InwardRelaunch(unittest.TestCase):
 def test_exact_four_boundaries_and_nonoverlap(self):
  for lane,start,end in [('EARLY_ASC','2000-01','2012-12'),('EARLY_DESC','2012-12','2000-01'),('RECENT_ASC','2013-01','2026-10'),('RECENT_DESC','2026-10','2013-01')]:
   m=lane_months(lane);self.assertEqual((m[0],m[-1]),(start,end));self.assertEqual(len(m),len(set(m)))
  self.assertFalse(set(lane_months('EARLY_ASC'))&set(lane_months('RECENT_ASC')))
 def test_get_504_retries_bounded(self):
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read=Mock(return_value=b'{"ok":true}');response.headers={}
  err=urllib.error.HTTPError('https://api.github.com/x',504,'timeout',{},None)
  with patch.object(b.urllib.request,'urlopen',side_effect=[err,response]) as call,patch.object(b.time,'sleep'):
   data,_=b.open_json(b.urllib.request.Request('https://api.github.com/x'))
   self.assertTrue(data['ok']);self.assertEqual(call.call_count,2)
 def test_mutation_not_replayed(self):
  err=urllib.error.URLError('timeout')
  with patch.object(b.urllib.request,'urlopen',side_effect=err) as call:
   with self.assertRaises(urllib.error.URLError):b.open_json(b.urllib.request.Request('https://api.github.com/x',method='POST'))
   self.assertEqual(call.call_count,1)
