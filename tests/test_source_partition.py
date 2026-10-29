import random,unittest
from scripts.v093_source_partition import COUNTS,partition
class SourcePartitionTests(unittest.TestCase):
 def rows(self,n=10):return [dict(source='TDCC',key=str(i),period=f'2025-{i+1:02d}',availability='PROVEN_APPLICABLE') for i in range(n)]
 def test_exact_eleven_slots_for_seven_sources(self):self.assertEqual((len(COUNTS),sum(COUNTS.values())),(7,11))
 def test_both_frontiers_cover_every_task_exactly_once(self):
  rows=self.rows();r=partition(rows,'TDCC','2026-10-29')
  self.assertFalse(set(r['latest_first'])&set(r['oldest_first']))
  self.assertEqual(set(r['latest_first']+r['oldest_first']),{x['key'] for x in rows})
  self.assertEqual(r['latest_first'][0],'9');self.assertEqual(r['oldest_first'][0],'0')
 def test_empty_odd_and_singleton_preserve_scope(self):
  for n in range(12):
   r=partition(self.rows(n),'TDCC','2026-10-29');self.assertEqual(len(r['latest_first'])+len(r['oldest_first']),n)
 def test_unknown_and_out_of_scope_remain_visible_instead_of_downloaded(self):
  rows=self.rows(3);rows[0]['period']='1999-12';rows[1]['period']='2026-11';rows[2]['availability']='UNCONFIRMED'
  r=partition(rows,'TDCC','2026-10-29');self.assertEqual(len(r['held']),3);self.assertEqual(r['latest_first'],[])
 def test_deterministic_restore_does_not_reassign_on_input_order(self):
  rows=self.rows();a=partition(rows,'TDCC','2026-10-29');random.Random(3).shuffle(rows)
  self.assertEqual(a,partition(rows,'TDCC','2026-10-29'))
 def test_cost_balance_is_not_calendar_midpoint(self):
  rows=self.rows();rows[-1]['estimated_cost']=9;r=partition(rows,'TDCC','2026-10-29')
  self.assertEqual(r['latest_first'],['9']);self.assertEqual((r['latest_cost'],r['oldest_cost']),(9,9))
 def test_duplicate_or_invalid_cost_is_rejected(self):
  rows=self.rows(1)
  with self.assertRaises(ValueError):partition(rows+rows,'TDCC','2026-10-29')
  for cost in (-1,0,float('nan'),True):
   rows[0]['estimated_cost']=cost
   with self.assertRaises(ValueError):partition(rows,'TDCC','2026-10-29')
 def test_source_isolation_and_small_source_has_no_empty_second_worker(self):
  rows=self.rows(2)+[dict(source='NDC',key='ndc',period='2026-08',availability='PROVEN_APPLICABLE')]
  r=partition(rows,'NDC','2026-10-29');self.assertEqual(r['latest_first'],['ndc']);self.assertEqual(r['oldest_first'],[])
