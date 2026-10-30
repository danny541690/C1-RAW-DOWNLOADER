"""Checksummed bounded pages, atomically referenced by one Git commit."""
import hashlib,json,re
SCHEMA='JARVIS_GITCAS_PAGED_V1'
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
def pack(state,page_bytes=1024*1024,max_bytes=512*1024*1024):
 if page_bytes<64 or max_bytes<1:raise ValueError('PAGE_LIMIT')
 tasks=state.get('tasks',{})
 if not isinstance(tasks,dict):raise ValueError('TASK_SCHEMA')
 files={};pages=[];current={};size=2;total=0
 def flush():
  nonlocal current,size,total
  if not current:return
  raw=encode(current);name=f'page-{len(pages):06d}.json';files[name]=raw;total+=len(raw)
  pages.append(dict(name=name,sha256=hashlib.sha256(raw).hexdigest(),count=len(current)))
  current={};size=2
 for key,value in sorted(tasks.items()):
  item_size=len(encode(key))+1+len(encode(value))+1
  if item_size+2>page_bytes:raise ValueError('SINGLE_TASK_EXCEEDS_PAGE_LIMIT')
  if size+item_size>page_bytes:flush()
  current[key]=value;size+=item_size
 flush()
 header=dict(state);header.pop('tasks',None)
 index=encode(dict(schema=SCHEMA,state=header,tasks_present='tasks' in state,pages=pages,task_count=len(tasks)))
 if len(index)>page_bytes:raise ValueError('STATE_HEADER_REQUIRES_COMPACTION')
 total+=len(index)
 if total>max_bytes:raise ValueError('STATE_TOTAL_SIZE_LIMIT')
 files['state.json']=index;return files
def unpack(index_raw,read,page_bytes=1024*1024,max_bytes=512*1024*1024):
 if len(index_raw)>page_bytes:raise ValueError('STATE_INDEX_SIZE_LIMIT')
 index=json.loads(index_raw)
 if index.get('schema')!=SCHEMA:raise ValueError('PAGE_SCHEMA')
 state=dict(index['state']);tasks={};total=len(index_raw);names=set()
 for page in index['pages']:
  name=page['name']
  if not re.fullmatch(r'page-\d{6}\.json',name) or name in names:raise ValueError('PAGE_NAME')
  names.add(name);raw=read(name);total+=len(raw)
  if len(raw)>page_bytes or total>max_bytes:raise ValueError('STATE_PAGE_SIZE_LIMIT')
  if hashlib.sha256(raw).hexdigest()!=page['sha256']:raise ValueError('STATE_PAGE_HASH_MISMATCH')
  values=json.loads(raw)
  if not isinstance(values,dict) or len(values)!=page['count'] or tasks.keys()&values.keys():raise ValueError('STATE_PAGE_TASK_CONFLICT')
  tasks.update(values)
 if len(tasks)!=index['task_count']:raise ValueError('STATE_TASK_COUNT_MISMATCH')
 if index['tasks_present']:state['tasks']=tasks
 return state
