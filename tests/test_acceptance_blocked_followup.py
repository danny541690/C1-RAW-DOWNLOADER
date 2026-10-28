import contextlib
import csv
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import v093_acceptance_blocked_followup as follow


class ExactFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.reg=self.root/'register';self.reg.mkdir();self.cache=self.root/'cache';self.cache.mkdir()
        self.raw=json.dumps(dict(status=200,data=[dict(date='2010-06-30',stock_id='1444',type='EPS',origin_name='每股盈餘',value=0.6)])).encode()
        self.row={'來源':'FinMind','單元ID':'unit1','資料集':'TaiwanStockFinancialStatements','原件參照':'file1',
                  'RAW_SHA256':follow.sha(self.raw),'期間':'2010-06','月份':'2010-06','代碼':'1444','已下載':'1'}
        self.old={'source':'FinMind','task_id':'unit1','period':'2010-06','raw_reference':'file1',
                  'raw_sha256':follow.sha(self.raw),'package_sha256':follow.sha(self.raw),'error':'ValueError:UNMAPPED_DATASET'}
        self.targets=self.root/'targets.csv'

    def write(self, targets=None):
        with self.targets.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.old);w.writeheader();w.writerows(targets or [self.old])
        with gzip.open(self.reg/'FinMind_units.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.row);w.writeheader();w.writerow(self.row)

    def run_follow(self, download=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return follow.run(self.targets,self.reg,self.cache,self.root/'out',download)

    def test_exact_frozen_task_is_rechecked_with_raw_bytes_unchanged(self):
        self.write();(self.cache/'file1').write_bytes(self.raw);result=self.run_follow()
        self.assertEqual(result['counts'],{'PARTIAL_CONTENT_NOT_RELEASED':1})
        self.assertEqual(result['raw_sha_verified_units'],1);self.assertEqual(result['approved_scopes'],[])
        self.assertEqual((self.cache/'file1').read_bytes(),self.raw)

    def test_changed_target_context_stops_before_remote_read(self):
        self.row['期間']='2010-09';self.write();calls=[]
        with self.assertRaisesRegex(ValueError,'CONTEXT_CHANGED'):self.run_follow(lambda fid:calls.append(fid))
        self.assertFalse(calls)

    def test_missing_frozen_task_is_not_reconstructed_or_downloaded(self):
        self.row['單元ID']='other';self.write();calls=[]
        with self.assertRaisesRegex(ValueError,'NOT_FOUND'):self.run_follow(lambda fid:calls.append(fid))
        self.assertFalse(calls)

    def test_duplicate_target_identity_rejected(self):
        self.write([self.old,self.old])
        with self.assertRaisesRegex(ValueError,'TARGET_SET'):self.run_follow()

    def test_hash_conflict_never_reaches_the_content_checker(self):
        self.write();(self.cache/'file1').write_bytes(b'corrupt')
        with patch.object(follow,'inspect_raw',side_effect=AssertionError('must not inspect')):
            result=self.run_follow()
        self.assertEqual(result['raw_sha_verified_units'],0);self.assertEqual(result['counts'],{'CONTENT_BLOCKED':1})
        self.assertEqual((self.cache/'file1').read_bytes(),b'corrupt')

    def test_downloaded_retained_file_is_bound_to_existing_sha(self):
        self.write();calls=[]
        result=self.run_follow(lambda fid:calls.append(fid) or self.raw)
        self.assertEqual(calls,['file1']);self.assertEqual(result['raw_sha_verified_units'],1)
        self.assertEqual(result['source_market_downloads'],0);self.assertEqual(result['production_writes'],0)


if __name__=='__main__':unittest.main()
