import csv,gzip,json,tempfile,unittest
from pathlib import Path
from scripts.v093_acceptance_progress import build_progress,render_progress

class ProgressTests(unittest.TestCase):
 def test_partial_and_missing_are_not_repairs_or_exceptions_and_fixes_accumulate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);queue=root/'queue.gz';prior=root/'progress.json'
   def write(statuses,sha='a'):
    with gzip.open(queue,'wt',encoding='utf-8',newline='') as f:
     w=csv.DictWriter(f,fieldnames=['task_key','source','period','raw_sha256','status','queue']);w.writeheader()
     for key,status in statuses:w.writerow(dict(task_key=key,source='MOPS',period='2001-03',raw_sha256=sha,status=status,queue='REVIEW'))
   write([('one','CONTENT_BLOCKED'),('two','REMAINING_RULES_OPEN'),('three','RECONCILE_FROZEN_MISSING')])
   p=build_progress(queue,{'MOPS':'sig'},[])
   self.assertEqual((p['required_items'],p['checked_items_count'],p['pending_items']),(3,2,3))
   self.assertEqual((p['repaired_items'],p['confirmed_exception_items'],p['completed_items']),(0,0,0))
   prior.write_text(json.dumps(p))
   write([('one','REMAINING_RULES_OPEN'),('two','RAW_NOT_IN_LOCAL_CACHE'),('three','RECONCILE_FROZEN_MISSING')])
   p=build_progress(queue,{'MOPS':'sig'},[],[prior])
   self.assertEqual((p['repaired_items'],p['newly_repaired_items'],p['reused_prior_checked_items']),(1,1,1))
   prior.write_text(json.dumps(p))
   p=build_progress(queue,{'MOPS':'sig'},[],[prior])
   self.assertEqual((p['repaired_items'],p['newly_repaired_items']),(1,0))
   self.assertIn('尚待處理',render_progress(p))
   p=build_progress(queue,{'MOPS':'changed'},[],[prior])
   self.assertEqual(p['reused_prior_checked_items'],0)
   self.assertEqual(p['invalidated_prior_items'],1)
   self.assertEqual(p['repaired_items'],0)

 def test_removed_tasks_are_not_counted_from_prior_reports(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);prior=root/'p.json';q=root/'q.gz'
   prior.write_text(json.dumps(dict(schema='JARVIS_INCREMENTAL_PROGRESS_V1',checked_items={'gone':{}})))
   with gzip.open(q,'wt') as f:f.write('task_key,source,period,raw_sha256,status,queue\nnew,TDCC,2025,a,RAW_NOT_IN_LOCAL_CACHE,READBACK_EXISTING\n')
   p=build_progress(q,{'TDCC':'sig'},[],[prior])
   self.assertEqual(p['checked_items_count'],0)
   self.assertEqual(p['unchecked_items'],1)

if __name__=='__main__':unittest.main()
