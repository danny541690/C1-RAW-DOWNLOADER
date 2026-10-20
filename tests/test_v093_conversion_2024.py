import json,unittest
from scripts.v093_operations import conversion_plan_2024,read_conversion_2024,repair_plan
from scripts.v093_parallel_worker import partition_items
from scripts.v093_standard_r4 import VERSION

class Year2024Conversion(unittest.TestCase):
    def test_twelve_months_descending_all_four_sources(self):
        plan=conversion_plan_2024();self.assertEqual(len(plan),12)
        self.assertEqual([i['key'] for i in plan],[f'2024-{m:02d}' for m in range(12,0,-1)])
        self.assertTrue(all(i['sources']==['TWSE','TPEx','MOPS','FinMind'] for i in plan))
    def test_year_queue_is_disjoint_from_existing_years(self):
        all_items=conversion_plan_2024()+repair_plan()
        selected=partition_items(all_items,'2024');self.assertEqual(len(selected),12)
        self.assertEqual(len(partition_items(all_items,'july')),1);self.assertEqual(len(partition_items(all_items,'financial')),21)
    def test_monitor_reads_independent_progress_and_rejects_wrong_year(self):
        plan=conversion_plan_2024();plan[0]['status']='STAGING_REPAIR_COMPLETE';plan[1]['status']='RUNNING'
        class D:
            def read(self,*a):return json.dumps({'version':VERSION,'lane':'2024','items':plan})
        status=read_conversion_2024(D(),'ops');self.assertEqual(status['complete'],1);self.assertEqual(status['total'],12);self.assertFalse(status['approved'])
        plan[0]['key']='2025-12'
        with self.assertRaisesRegex(ValueError,'SCOPE_CONFLICT'):read_conversion_2024(D(),'ops')
    def test_monitor_does_not_count_empty_unscheduled_queue_as_complete(self):
        class D:
            def read(self,*a):return None
        status=read_conversion_2024(D(),'ops');self.assertEqual(status['complete'],0);self.assertEqual(len(status['items']),12)

    def test_month_metadata_cannot_silently_point_at_a_different_year_or_scope(self):
        plan=conversion_plan_2024()
        class D:
            def read(self,*a):return json.dumps({'version':VERSION,'lane':'2024','items':plan})
        plan[0]['year']=2025
        with self.assertRaisesRegex(ValueError,'UNIT_CONFLICT'):read_conversion_2024(D(),'ops')
        plan[0]['year']=2024;plan[0]['sources']=['FinMind']
        with self.assertRaisesRegex(ValueError,'UNIT_CONFLICT'):read_conversion_2024(D(),'ops')

if __name__=='__main__':unittest.main()
