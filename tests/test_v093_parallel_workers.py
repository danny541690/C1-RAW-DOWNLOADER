import datetime as dt,json,unittest,hashlib,io
from unittest.mock import patch
import pyarrow as pa,pyarrow.parquet as pq
from scripts.v093_feature_warmup import prepare
from scripts.v093_operations import repair_plan,merged_repair_queue
from scripts.v093_parallel_worker import partition_items,legacy_controller_active
from scripts.v093_feature_warmup import warmup_rows
from scripts.v093_standard_r4 import VERSION
from scripts.v093_folder_registry import FolderRegistry

class ParallelAcceptance(unittest.TestCase):
    def test_migration_keeps_checkpoint_and_partitions_all_months_once(self):
        items=repair_plan();items[0].update(status='CHECKPOINTED',run_id='saved')
        a=partition_items(items,'july');b=partition_items(items,'financial')
        self.assertEqual(a[0]['run_id'],'saved');self.assertEqual(len(a),1);self.assertEqual(len(b),21)
        self.assertEqual({i['key'] for i in a}&{i['key'] for i in b},set())
        b[0].update(status='CHECKPOINTED',finished_at='2026-10-20')
        self.assertNotEqual(partition_items(b,'financial')[0]['key'],b[0]['key'])
    def test_monitor_reads_shards_without_losing_other_lane(self):
        plan=repair_plan();j=partition_items(plan,'july');j[0]['status']='STAGING_REPAIR_COMPLETE'
        class D:
            def read(self,p,n):return json.dumps({'version':VERSION,'lane':'july','items':j}) if 'JULY' in n else None
        result=merged_repair_queue(D(),'ops',{'items':plan})
        self.assertEqual(len(result['items']),22);self.assertEqual(result['items'][0]['status'],'STAGING_REPAIR_COMPLETE')
    def test_wrong_lane_shard_cannot_overwrite_scope(self):
        class D:
            def read(self,p,n):return json.dumps({'version':VERSION,'lane':'july','items':repair_plan()})
        with self.assertRaises(ValueError):merged_repair_queue(D(),'ops',{'items':repair_plan()})
    def test_old_writer_defers_new_workers(self):
        runs=[{'path':'.github/workflows/v093-operational-control.yml','status':'in_progress','head_sha':'old'}]
        self.assertTrue(legacy_controller_active(runs,'new'));runs[0]['status']='completed'
        self.assertFalse(legacy_controller_active(runs,'new'))
    def test_worker_registry_does_not_write_controller_registry(self):
        class D:
            written=[]
            def read(self,p,n):return None
            def put(self,p,n,b,*args,**kw):self.written.append(n)
        d=D();r=FolderRegistry(d,'qa',namespace='JULY');r.pending={'p/n':{'canonical_id':'id'}};r.flush()
        self.assertEqual(d.written,['FOLDER_ID_REGISTRY_V1_JULY.json'])
    def test_independent_linear_series_golden_and_no_future_input(self):
        start=dt.date(2026,1,1)
        points=[{'stock_id':'2330','date':(start+dt.timedelta(days=i)).isoformat(),'close':str(i+1)} for i in range(260)]
        rows,conflicts=warmup_rows(points,target='2026-09');r=next(x for x in rows if x['date']==(start+dt.timedelta(days=249)).isoformat())
        self.assertEqual(r['ma_240'],'130.5');self.assertEqual(r['return_240'],'2400');self.assertEqual(conflicts,0)
        rows2,_=warmup_rows(points[:250],target='2026-09');self.assertEqual(rows2[-1],r)
    def test_conflicting_instrument_quarantined_and_short_history_null(self):
        p=[{'stock_id':'A','date':'2026-09-01','close':'1'},{'stock_id':'A','date':'2026-09-01','close':'2'},{'stock_id':'B','date':'2026-09-01','close':'3'}]
        rows,c=warmup_rows(p);self.assertEqual(c,1);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['stock_id'],'B');self.assertIsNone(rows[0]['ma_240'])

    def test_warmup_input_hash_cache_and_output_roundtrip(self):
        buf=io.BytesIO();pq.write_table(pa.Table.from_pylist([{'date':'2026-09-01','stock_id':'2330','native_field':'收盤價','numeric_decimal_text':'100','date_content_verified':True,'status':'STAGING_UNMAPPED'}]),buf)
        payload=buf.getvalue();digest=hashlib.sha256(payload).hexdigest()
        class Registry:
            def folder(self,parent,name,create=False):return parent+'/'+name
            def flush(self):pass
        class D:
            data={};input_reads=0
            def read(self,parent,name):
                if name.endswith('_AUDIT.json'):return json.dumps({'status':'STAGING_NOT_APPROVED','archives':[{'source':'TWSE','parquet_name':'input.parquet','parquet_sha256':digest}]})
                if name=='input.parquet':self.input_reads+=1;return payload
                return self.data.get((parent,name))
            def put(self,parent,name,body,*args,**kw):self.data[(parent,name)]=body
        d=D()
        with patch('scripts.v093_feature_warmup.PERIODS',('2026-09',)):
            first=prepare(d,Registry(),'qa','ops');second=prepare(d,Registry(),'qa','ops')
        self.assertEqual(first['rows'],1);self.assertEqual(second['rows'],1);self.assertEqual(d.input_reads,1)
        self.assertFalse(second['approved']);self.assertEqual(second['rows_with_ma240'],0)
        key=next(k for k in d.data if k[1].endswith('.json') and 'CACHE' in k[0]);d.data[key]=b'changed'
        with patch('scripts.v093_feature_warmup.PERIODS',('2026-09',)):
            with self.assertRaisesRegex(ValueError,'CACHE_HASH_MISMATCH'):prepare(d,Registry(),'qa','ops')

if __name__=='__main__':unittest.main()
