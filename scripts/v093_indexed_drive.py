"""Batch-local positive file index; content/hash validation stays unchanged.

Use only within an already serialized writer. New names always get a fresh query;
existing duplicate names in a folder snapshot remain blocking.
"""
import collections,time,hashlib
from scripts.annual_actual_firstpass import Drive

class IndexedDrive(Drive):
    def __init__(self,api):
        super().__init__(api);self.indexes={};self.stats=collections.Counter()
    def call(self,make_request):
        started=time.perf_counter()
        def counted():
            request=make_request();self.stats['api_requests']+=1
            self.stats['request_'+str(getattr(request,'methodId','unknown'))]+=1
            return request
        try:
            result=super().call(counted)
            if isinstance(result,bytes):self.stats['downloaded_bytes']+=len(result)
            return result
        finally:self.stats['api_call_seconds']+=time.perf_counter()-started
    def find(self,parent,name):
        if parent not in self.indexes:
            index=collections.defaultdict(list);page=None
            while True:
                result=self.call(lambda:self.api.files().list(q="'"+parent+"' in parents and trashed = false",fields='nextPageToken,files(id,name,mimeType,size)',pageSize=1000,pageToken=page))
                for item in result.get('files',[]):index[item['name']].append(item)
                page=result.get('nextPageToken')
                if not page:break
            self.indexes[parent]=index
        items=self.indexes[parent].get(name,[])
        if len(items)>1:raise ValueError('duplicate remote names')
        if items:self.stats['positive_index_hits']+=1;return items[0]
        # Do not cache absence: a successful create needs immediate readback,
        # and a timed-out create must recover the server's actual file ID.
        self.stats['fresh_name_lookups']+=1
        found=super().find(parent,name)
        if found:self.indexes[parent][name]=[found]
        return found
    def read(self,parent,name):
        try:return super().read(parent,name)
        except ValueError as exc:
            if str(exc)!='duplicate remote names' or not name.endswith(('.receipt.json','.parquet')):raise
            # Only immutable conversion artifacts qualify. Never select by recency.
            items=self.indexes[parent][name]
            bodies=[self.call(lambda item=item:self.api.files().get_media(fileId=item['id'])) for item in items]
            if len({hashlib.sha256(body).digest() for body in bodies})!=1:
                raise ValueError('DUPLICATE_IMMUTABLE_CONTENT_CONFLICT '+name)
            self.stats['identical_duplicate_reads_verified']+=1
            return bodies[0]
    def put(self,*args,**kwargs):
        self.stats['put_calls']+=1;started=time.perf_counter()
        try:return super().put(*args,**kwargs)
        finally:self.stats['put_wall_seconds_includes_readbacks']+=time.perf_counter()-started

class CheckpointThrottle:
    def __init__(self,seconds=60,items=10,clock=time.monotonic):
        self.seconds=seconds;self.items=items;self.clock=clock;self.last=None;self.pending=0
    def due(self,force=False):
        self.pending+=1;now=self.clock()
        if force or self.last is None or self.pending>=self.items or now-self.last>=self.seconds:
            self.last=now;self.pending=0;return True
        return False
