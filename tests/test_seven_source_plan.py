import copy,json,unittest
from pathlib import Path
from scripts.v093_seven_source_plan import SOURCES,months_desc,validate_config,build_plan,eligible_gap

class SevenSourcePlanTests(unittest.TestCase):
 def setUp(self):self.c=json.loads(Path('config/v093_seven_source_design.json').read_text())
 def test_full_scope_descending_and_current_month_is_partial(self):
  m=months_desc('2026-10-29');self.assertEqual((len(m),m[0],m[-1]),(322,'2026-10','2000-01'))
  self.assertEqual(len(m),len(set(m)));self.assertEqual(m,sorted(m,reverse=True))
 def test_exact_sources_and_exclusive_state_ownership(self):
  validate_config(self.c)
  c=copy.deepcopy(self.c);c['lanes'][1]['state_branch']=c['lanes'][0]['state_branch']
  with self.assertRaises(ValueError):validate_config(c)
 def test_directions_share_runtime_authority_not_legacy_projections(self):
  for slot in self.c['slots']:
   self.assertEqual(slot['coordination_state_branch'],'jarvis-source-state/'+slot['source'])
  c=copy.deepcopy(self.c);c['slots'][0]['coordination_state_branch']=c['slots'][0]['state_branch']
  with self.assertRaisesRegex(ValueError,'SOURCE_COORDINATION_BRANCH'):validate_config(c)
 def test_no_preview_can_activate_or_reset_retry_budget(self):
  for field,value in [('activate_production',True),('direction','ASC')]:
   c=copy.deepcopy(self.c);c[field]=value
   with self.assertRaises(ValueError):validate_config(c)
  c=copy.deepcopy(self.c);c['attempts']['reset_on_restart']=True
  with self.assertRaises(ValueError):validate_config(c)
 def test_finmind_rejects_old_missing_flags_and_unproven_semantics(self):
  g=dict(official_source='TWSE',official_evidence_id='evidence',confirmed_gap=True,
   period='2026-10-28',identity_period_market_verified=True,definition_unit_frequency_verified=True,
   stock_id='2330',dataset='TaiwanStockPrice')
  self.assertTrue(eligible_gap(g,'2026-10-29'))
  for k,v in [('official_evidence_id',None),('confirmed_gap',False),('period','2026-10-30'),('definition_unit_frequency_verified',False),('official_source','FinMind')]:
   bad=dict(g);bad[k]=v;self.assertFalse(eligible_gap(bad,'2026-10-29'))
  self.assertEqual(build_plan(self.c,'FinMind','2026-10-29',[g])['eligible_finmind_gap_tasks'],1)
 def test_bidirectional_slots_only_for_large_sources(self):
  r=build_plan(self.c,'TDCC','2026-10-29',direction='ASC')
  self.assertEqual(r['month_priority'][0],'2000-01')
  with self.assertRaises(ValueError):build_plan(self.c,'NDC','2026-10-29',direction='ASC')

 def test_previews_do_not_pretend_months_are_verified_tasks(self):
  for source in SOURCES:
   r=build_plan(self.c,source,'2026-10-29')
   self.assertEqual((r['market_requests'],r['production_writes']),(0,0))
   self.assertTrue(r['readiness_blockers']);self.assertFalse(r['month_count_is_expected_data_unit_denominator'])
 def test_twelve_manual_workflows_have_no_live_schedule_or_source_secret(self):
  paths=list(Path('.github/workflows').glob('jarvis-seven-*-preview.yml'));self.assertEqual(len(paths),12)
  for p in paths:
   s=p.read_text();self.assertIn('workflow_dispatch:',s);self.assertNotIn('schedule:',s)
   self.assertNotIn('secrets.',s);self.assertIn('uses: ./.github/workflows/jarvis-seven-worker.yml',s);self.assertIn('default: entry-validation',s)
