import datetime as dt,json,unittest,hashlib,io
from unittest.mock import patch
import pyarrow as pa,pyarrow.parquet as pq
from scripts.v093_feature_warmup import prepare,read_verified_cache
from scripts.v093_operations import repair_plan,merged_repair_queue
from scripts.v093_parallel_worker import partition_items,legacy_controller_active,upgrade_parser_queue
from scripts.v093_feature_warmup import warmup_rows
from scripts.v093_standard_r4 import VERSION,PARSER_REVISION,parse_member,receipt_key
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

    def slice_envelope(self):
        return {'dataset':'TaiwanStockPrice','stock_id':'2330','response_sha256':'a'*64,'annual_query_dates':['2026-01-01','2026-10-19'],'query_source':'FinMind_Free_Token','status':'RAW_MONTH_SLICE_NOT_PIT_VERIFIED','rows':[{'date':'2026-09-01','stock_id':'2330','open':100,'max':103,'min':99,'close':102,'Trading_Volume':2000}]}
    def test_actual_downloader_slice_contract_retains_native_rows(self):
        obj=self.slice_envelope();out,stats,_=parse_member('FinMind','TaiwanStockPrice/2330.json',json.dumps(obj).encode(),'2026-09')
        self.assertEqual(stats['NATIVE_RECORDS'],1);self.assertEqual(stats['OHLC_CHECKED_ROWS'],1)
        close=next(r for r in out if r['native_field']=='close');self.assertEqual(close['numeric_decimal_text'],'102');self.assertEqual(json.loads(close['native_record_json']),obj['rows'][0]);self.assertFalse(close['pit_verified'])
    def test_slice_rejects_scope_conflict_and_outside_month(self):
        obj=self.slice_envelope();obj['rows'][0]['stock_id']='1101'
        with self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):parse_member('FinMind','2330.json',json.dumps(obj).encode(),'2026-09')
        obj=self.slice_envelope();out,stats,_=parse_member('FinMind','2330.json',json.dumps(obj).encode(),'2026-08')
        self.assertEqual(out,[]);self.assertEqual(stats['OUTSIDE_PARTITION'],1)
    def test_slice_requires_provenance_and_unambiguous_container(self):
        for change in ({'response_sha256':'invalid'},{'data':[{'stock_id':'2330'}]},{'status':'APPROVED'}):
            obj=self.slice_envelope();obj.update(change)
            with self.assertRaises(ValueError):parse_member('FinMind','2330.json',json.dumps(obj).encode(),'2026-09')
    def test_parser_upgrade_requeues_completed_finmind_once_and_keeps_other_receipts(self):
        q={'items':[{'status':'STAGING_REPAIR_COMPLETE'},{'status':'CHECKPOINTED','run_id':'saved'}]}
        upgrade_parser_queue(q);self.assertEqual(q['items'][0]['status'],'PENDING');self.assertEqual(q['items'][1]['run_id'],'saved')
        q['items'][0]['status']='STAGING_REPAIR_COMPLETE';upgrade_parser_queue(q);self.assertEqual(q['items'][0]['status'],'STAGING_REPAIR_COMPLETE')
        raw_sha='a'*64;self.assertEqual(receipt_key('TWSE',raw_sha),hashlib.sha256(('TWSE'+VERSION+raw_sha).encode()).hexdigest())
        self.assertNotEqual(receipt_key('FinMind',raw_sha),hashlib.sha256(('FinMind'+VERSION+raw_sha).encode()).hexdigest())

    def alias_drive(self,bodies):
        class API:
            def files(self):return self
            def get_media(self,fileId):return bodies[fileId]
        class D:
            api=API()
            def read(self,*args):raise ValueError('duplicate remote names')
            def call(self,fn):return fn()
        return D()
    def test_identical_live_cache_aliases_resume_by_recorded_hash(self):
        payload=b'{"input_sha256":"original","points":[]}'
        d=self.alias_drive({'one':payload,'two':payload});receipt={'cache_sha256':hashlib.sha256(payload).hexdigest()}
        with patch('scripts.v093_feature_warmup.ls',return_value=[{'name':'cache.json','id':'two'},{'name':'cache.json','id':'one'}]):
            body,ids=read_verified_cache(d,'folder','cache.json',receipt)
        self.assertEqual(body,payload);self.assertEqual(ids,['one','two'])
    def test_conflicting_cache_aliases_are_not_chosen_arbitrarily(self):
        d=self.alias_drive({'one':b'correct','two':b'changed'})
        with patch('scripts.v093_feature_warmup.ls',return_value=[{'name':'cache.json','id':'one'},{'name':'cache.json','id':'two'}]):
            with self.assertRaisesRegex(ValueError,'CONFLICTING_CACHE_ALIASES'):read_verified_cache(d,'folder','cache.json')

if __name__=='__main__':unittest.main()
