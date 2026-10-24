import copy,json,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
from scripts import v093_four_lane_month_acceptance as flow

class MemoryDrive:
    test_memory_backend=True
    def __init__(self):
        self.items={};self.blobs={};self.next_id=0
        self.api=SimpleNamespace(files=lambda:SimpleNamespace(get_media=lambda fileId:self.blobs[fileId]))
    def call(self,f):return f()
    def find(self,p,n):return self.items.get((p,n))
    def folder(self,p,n):
        if (p,n) not in self.items:
            self.next_id+=1;self.items[p,n]=dict(id=str(self.next_id),mimeType='application/vnd.google-apps.folder')
        return self.items[p,n]['id']
    def read(self,p,n):
        x=self.find(p,n);return self.blobs[x['id']] if x else None
    def put(self,p,n,raw,*args,overwrite=False,**kwargs):
        old=self.find(p,n)
        if old and not overwrite:
            if self.blobs[old['id']]!=raw:raise ValueError('IMMUTABLE_MISMATCH')
            return
        if old:fid=old['id']
        else:
            self.next_id+=1;fid=str(self.next_id);self.items[p,n]=dict(id=fid,mimeType='application/octet-stream')
        self.blobs[fid]=bytes(raw)

class FourLaneMonthlyFlowTests(unittest.TestCase):
    def test_real_worker_month_flow_pause_retry_and_no_raw_duplicates(self):
        d=MemoryDrive();parent=d.folder('root','sandbox');store={'jobs':{}};version=[0]
        def read(*args):return str(version[0]),copy.deepcopy(store)
        def put(api,token,sha,payload,message):
            if sha!=str(version[0]):return False
            store.clear();store.update(copy.deepcopy(payload));version[0]+=1;return True
        with patch.object(flow,'sandbox',return_value=parent), \
             patch.object(flow.gate,'_read',side_effect=read),patch.object(flow.gate,'_put',side_effect=put), \
             patch.object(flow.coord,'_read',side_effect=read),patch.object(flow.coord,'_put',side_effect=put), \
             patch.object(flow.repair,'reserve_source',return_value=True):
            flow.seed(d,'100','api','token');root=flow.scope(d,'100')
            before={key:copy.deepcopy(value) for key,value in d.items.items() if key[1].startswith('SYNTHETIC_')}
            for lane in flow.MONTHS:flow.worker(d,root,'api','token','100',lane,'frontier')
            flow.verify(d,root,'api','token','frontier')
            time.sleep(3.2)  # Actual sandbox cooldown; no backdating of leases.
            for lane in flow.MONTHS:flow.worker(d,root,'api','token','100',lane,'resume')
            flow.verify(d,root,'api','token','resume')
            for key,value in before.items():self.assertEqual(d.items[key],value)
            ids={key:value['id'] for key,value in d.items.items() if key[1].endswith('.zip')}
            for lane in flow.MONTHS:flow.worker(d,root,'api','token','100',lane,'resume')
            self.assertEqual(ids,{key:value['id'] for key,value in d.items.items() if key[1].endswith('.zip')})
            for lane in flow.MONTHS:
                result=flow.load(d,flow.existing_folder(d,root,lane),'FLOW_RESUME.json')
                self.assertEqual(result['simulated_source_calls'],0)
            result=flow.load(d,root,'FLOW_VERIFY_RESUME.json')
            self.assertEqual(result['counts']['saved_and_readback_verified_units'],12)
            self.assertEqual(result['production_data_writes'],0)

if __name__=='__main__':unittest.main()
