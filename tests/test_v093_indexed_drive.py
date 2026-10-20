import hashlib,unittest
from scripts.annual_actual_firstpass import Drive
from scripts.v093_indexed_drive import IndexedDrive,CheckpointThrottle

class Request:
    def __init__(self,api,kind,fn):self.api=api;self.methodId='drive.files.'+kind;self.kind=kind;self.fn=fn
    def execute(self,**kwargs):
        self.api.counts[self.kind]=self.api.counts.get(self.kind,0)+1;return self.fn()
class API:
    def __init__(self,items):self.items=list(items);self.counts={};self.bodies={'a':b'verified immutable bytes'}
    def files(self):return self
    def list(self,**kw):
        def result():
            rows=self.items
            if kw['q'].startswith('name = '):rows=[r for r in rows if r['name']==kw['q'].split("'")[1]]
            return {'files':rows}
        return Request(self,'list',result)
    def get_media(self,fileId):return Request(self,'get',lambda:self.bodies[fileId])

class IndexedDriveAcceptance(unittest.TestCase):
    def item(self,name='existing',id='a'):return {'id':id,'name':name,'mimeType':'application/octet-stream','size':'24'}
    def test_repeated_metadata_lookups_reduce_network_calls_without_changing_identity(self):
        slowapi=API([self.item()]);fastapi=API([self.item()]);slow=Drive(slowapi);fast=IndexedDrive(fastapi)
        for _ in range(100):self.assertEqual(slow.find('parent','existing'),fast.find('parent','existing'))
        self.assertEqual(slowapi.counts['list'],100);self.assertEqual(fastapi.counts['list'],1)
    def test_readback_still_fetches_actual_bytes_every_time(self):
        api=API([self.item()]);d=IndexedDrive(api)
        first=d.read('parent','existing');api.bodies['a']=b'changed bytes';second=d.read('parent','existing')
        self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest());self.assertEqual(api.counts['get'],2)
    def test_new_name_is_not_negatively_cached(self):
        api=API([self.item()]);d=IndexedDrive(api);self.assertIsNone(d.find('parent','new'))
        api.items.append(self.item('new','b'));self.assertEqual(d.find('parent','new')['id'],'b')
    def test_duplicate_names_remain_blocking(self):
        d=IndexedDrive(API([self.item(),self.item(id='b')]))
        with self.assertRaisesRegex(ValueError,'duplicate remote names'):d.find('parent','existing')
    def test_identical_immutable_duplicates_require_all_bytes_to_match(self):
        api=API([self.item('x.receipt.json'),self.item('x.receipt.json','b')]);api.bodies['b']=api.bodies['a']
        d=IndexedDrive(api);self.assertEqual(d.read('parent','x.receipt.json'),api.bodies['a'])
        api.bodies['b']=b'conflicting bytes'
        with self.assertRaisesRegex(ValueError,'CONTENT_CONFLICT'):d.read('parent','x.receipt.json')
        with self.assertRaisesRegex(ValueError,'duplicate remote names'):d.find('parent','x.receipt.json')
    def test_mutable_duplicate_reports_stay_blocked_even_when_identical(self):
        api=API([self.item('LATEST.json'),self.item('LATEST.json','b')]);api.bodies['b']=api.bodies['a']
        with self.assertRaisesRegex(ValueError,'duplicate remote names'):IndexedDrive(api).read('parent','LATEST.json')
    def test_checkpoint_limit_and_forced_error_or_boundary_flush(self):
        now=[0];throttle=CheckpointThrottle(seconds=60,items=10,clock=lambda:now[0]);self.assertTrue(throttle.due())
        for _ in range(9):self.assertFalse(throttle.due())
        self.assertTrue(throttle.due());now[0]=61;self.assertTrue(throttle.due());self.assertTrue(throttle.due(force=True))

if __name__=='__main__':unittest.main()
