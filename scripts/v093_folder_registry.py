"""Resolve duplicate folder names without moving or deleting any user content."""
import datetime,json
from scripts.v093_standard_r1 import ls

def choose_folder(candidates, child_counts, registered_id=None):
    ids={x['id'] for x in candidates}
    if registered_id:
        if registered_id not in ids:raise ValueError('REGISTERED_FOLDER_NOT_IN_PARENT')
        return registered_id,'REGISTERED_ID'
    if len(candidates)==1:return candidates[0]['id'],'UNIQUE_NAME'
    nonempty=[x['id'] for x in candidates if child_counts.get(x['id'],0)>0]
    if len(nonempty)==1:return nonempty[0],'ONLY_NONEMPTY_ALIAS'
    raise ValueError('AMBIGUOUS_FOLDER_IDS_REQUIRE_RECONCILIATION')

class FolderRegistry:
    def __init__(self,drive,control):
        self.d=drive;self.control=control;self.name='FOLDER_ID_REGISTRY_V1.json'
        raw=drive.read(control,self.name);self.data=json.loads(raw) if raw else {'version':1,'entries':{}}
        self.cache={};self.pending={}
    def flush(self):
        if not self.pending:return
        latest=self.d.read(self.control,self.name)
        data=json.loads(latest) if latest else {'version':1,'entries':{}}
        for key,record in self.pending.items():
            saved=data['entries'].get(key,{})
            if saved.get('canonical_id') not in (None,record['canonical_id']):raise ValueError('CANONICAL_REGISTRY_CONFLICT')
            data['entries'][key]=record
        data['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.d.put(self.control,self.name,json.dumps(data,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
        self.data=data;self.pending={}
    def folder(self,parent,name,create=False):
        key=parent+'/'+name
        if key in self.cache:return self.cache[key]
        found=[x for x in ls(self.d,parent) if x['name']==name and x['mimeType']=='application/vnd.google-apps.folder']
        if not found:
            if not create:raise FileNotFoundError(name)
            self.d.folder(parent,name)
            found=[x for x in ls(self.d,parent) if x['name']==name and x['mimeType']=='application/vnd.google-apps.folder']
        existing=self.data['entries'].get(key,{})
        counts={x['id']:len(ls(self.d,x['id'])) for x in found} if len(found)>1 else {}
        chosen,reason=choose_folder(found,counts,existing.get('canonical_id'))
        record={'canonical_id':chosen,'alias_ids':sorted(x['id'] for x in found if x['id']!=chosen),'reason':reason,'child_counts':counts}
        if existing.get('canonical_id')!=chosen or existing.get('alias_ids')!=record['alias_ids']:
            self.data['entries'][key]=record
            self.pending[key]=record
            # Resolve aliases durably before any output write. Batch ordinary IDs.
            if len(found)>1:self.flush()
        self.cache[key]=chosen
        return chosen
