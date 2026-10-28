"""Two cold-job CLI rounds, with three subprocess workers and real local Git.

Only the Google transport is a fixture. No production credentials are exercised.
"""
import base64
import concurrent.futures
import csv
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from scripts.v093_acceptance_remote_inventory import ROOT


class ScheduledCliRehearsal(unittest.TestCase):
    def test_two_fresh_job_rounds_resume_from_real_git_without_second_round_raw_reads(self):
        code_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            remote = p / 'remote.git'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            register, esb = p / 'register', p / 'esb'
            register.mkdir(); esb.mkdir()
            (esb / 'manifest.json').write_text('{"inputs": []}')
            files, rows = {}, []
            for i in range(9):
                fid = f'cli_package_{i}'
                raw = json.dumps({'status': 200, 'data': [dict(date='2000-01-04', stock_id='1515',
                                 open=10, max=12, min=9, close=11)]}).encode()
                meta = dict(id=fid, name=fid + '.json', mimeType='application/json', size=str(len(raw)),
                            md5Checksum=hashlib.md5(raw).hexdigest(), modifiedTime='2026-10-28T00:00:00Z',
                            version='1', parents=['sourceFM'])
                files[fid] = dict(metadata=meta, payload=base64.b64encode(raw).decode())
                rows.append({'來源': 'FinMind', '單元ID': fid, '資料集': 'TaiwanStockPrice',
                             '原件參照': fid, '已下載': '1', '年份': '2000', '月份': '2000-01',
                             '期間': '2000-01', '代碼': '1515', 'RAW_SHA256': hashlib.sha256(raw).hexdigest()})
            with gzip.open(register / 'FinMind_units.csv.gz', 'wt', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
            fixture, journal = p / 'fixture.json', p / 'transport.jsonl'
            fixture.write_text(json.dumps(dict(files=files, root=ROOT)))
            bootstrap = p / 'bootstrap.py'
            bootstrap.write_text(textwrap.dedent('''
                import base64,json,os,sys,types
                from pathlib import Path
                data=json.loads(Path(os.environ['REHEARSAL_FIXTURE']).read_text())
                def record(kind,fid=None):
                    with open(os.environ['REHEARSAL_JOURNAL'],'a') as stream:
                        stream.write(json.dumps(dict(kind=kind,id=fid))+'\\n')
                def request(value):
                    return types.SimpleNamespace(execute=lambda **kw:value)
                class Files:
                    def list(self,**kw):
                        record('list');q=kw['q']
                        if "'"+data['root']+"' in parents" in q:
                            rows=[dict(id='year2000',name='2000',mimeType='application/vnd.google-apps.folder',parents=[data['root']])]
                        elif "'year2000' in parents" in q:
                            rows=[dict(id='sourceFM',name='FinMind',mimeType='application/vnd.google-apps.folder',parents=['year2000'])]
                        else:rows=[x['metadata'] for x in data['files'].values()]
                        return request(dict(files=rows))
                    def get_media(self,fileId):
                        record('get_media',fileId)
                        return base64.b64decode(data['files'][fileId]['payload'])
                    def get(self,fileId,**kw):
                        return request(data['files'][fileId]['metadata'])
                class Download:
                    def __init__(self,buffer,payload,**kw):self.buffer=buffer;self.payload=payload
                    def next_chunk(self,**kw):self.buffer.write(self.payload);return None,True
                sys.modules['scripts.annual_actual_firstpass']=types.SimpleNamespace(service=lambda:types.SimpleNamespace(files=Files))
                sys.modules['googleapiclient.http']=types.SimpleNamespace(MediaIoBaseDownload=Download)
                from scripts import v093_acceptance_scheduler as worker
                worker.time.sleep=lambda seconds:None
                worker.main()
            '''))
            env = dict(os.environ, PYTHONPATH=str(code_root) + os.pathsep + os.environ.get('PYTHONPATH', ''),
                       REHEARSAL_FIXTURE=str(fixture), REHEARSAL_JOURNAL=str(journal))
            env.pop('GITHUB_STEP_SUMMARY', None)
            def execute(command, cwd, environment=env):
                completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=60)
                if completed.returncode:
                    self.fail(completed.stderr[-4000:] + completed.stdout[-1000:])
                return completed
            def prepare(job, lane):
                job.mkdir()
                execute(['git', 'init'], job)
                execute(['git', 'remote', 'add', 'origin', str(remote)], job)
                execute([sys.executable, '-m', 'scripts.v093_acceptance_state', 'restore', '--lane', lane,
                         '--directory', 'durable', '--lease', 'lease.json'], job)
            rounds = []
            for round_number in (1, 2):
                run = p / f'round-{round_number}'; run.mkdir()
                inventory = run / 'inventory'
                prepare(inventory, 'inventory')
                execute([sys.executable, str(bootstrap), '--inventory-only', '--state', 'durable',
                         '--lease', 'lease.json', '--out', 'results'], inventory)
                def run_worker(index):
                    job = run / f'worker-{index}'
                    prepare(job, f'worker-{index}')
                    execute([sys.executable, str(bootstrap), '--state', 'durable', '--lease', 'lease.json',
                             '--inventory-state', str(inventory / 'durable'), '--shard-index', str(index),
                             '--register', str(register), '--esb-evidence', str(esb), '--out', 'results'], job)
                    return json.loads((job / 'results/summary.json').read_text())
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                    summaries = list(pool.map(run_worker, range(3)))
                self.assertTrue(all(s['slice']['status'] == 'SLICE_COMPLETE_NOT_FULL_ACCEPTANCE' for s in summaries))
                execute([sys.executable, '-m', 'scripts.v093_acceptance_summary', '--reports', str(run),
                         '--out', 'combined.json'], run,
                        dict(env, INVENTORY_RESULT='success', CONTENT_RESULT='success'))
                combined = json.loads((run / 'combined.json').read_text())
                self.assertEqual(combined['reported_workers'], 3)
                self.assertEqual(combined['pipeline_status'], 'PARTIAL_EVIDENCE_NOT_FULL_ACCEPTANCE')
                self.assertEqual(combined['approved_scopes'], [])
                rounds.append(combined)
            events = [json.loads(line) for line in journal.read_text().splitlines()]
            reads = [e['id'] for e in events if e['kind'] == 'get_media']
            self.assertEqual(len(reads), 9)
            self.assertEqual(len(set(reads)), 9)
            self.assertEqual(sum(e['kind'] == 'list' for e in events), 3)
            self.assertEqual(rounds[0]['inspected_this_run'], 9)
            self.assertEqual(rounds[1]['inspected_this_run'], 0)
            self.assertEqual(sum(s['slice']['reused'] for s in summaries), 9)
            heads = execute(['git', 'ls-remote', '--heads', 'origin'], run / 'inventory').stdout
            self.assertEqual(heads.count('refs/heads/jarvis-acceptance-state/'), 4)
            self.assertNotIn('refs/heads/main', heads)


if __name__ == '__main__':
    unittest.main()
