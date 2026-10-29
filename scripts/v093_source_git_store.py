"""Durable per-source CAS over isolated Git branches; never force-pushes.

Uses the checkout's existing Git authentication. Values contain control state,
not credentials or RAW bytes. Each operation avoids checkout/index/FETCH_HEAD.
"""
import json,re,subprocess,uuid
from pathlib import Path
from scripts.v093_source_coordination import SOURCES
from scripts.v093_source_state_pages import pack,unpack,SCHEMA
class StoreUnavailable(RuntimeError):pass

class GitCAS:
 def __init__(self,repo,prefix='jarvis-source-state',max_bytes=512*1024*1024,page_bytes=1024*1024):
  self.repo=Path(repo);self.prefix=prefix;self.max_bytes=max_bytes;self.page_bytes=page_bytes
  if prefix!='jarvis-source-state' and not re.fullmatch(r'jarvis-source-preflight/[0-9A-Za-z_-]+',prefix):raise ValueError('QA_BRANCH_NAMESPACE_ONLY')
 def git(self,*args,data=None,check=True):
  p=subprocess.run(['git',*args],cwd=self.repo,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if check and p.returncode:raise StoreUnavailable('GIT_'+args[0].upper()+'_FAILED')
  return p
 def ref(self,source):
  if source not in SOURCES:raise ValueError('SOURCE_SCOPE')
  return 'refs/heads/'+self.prefix+'/'+source
 def remote_head(self,source):
  p=self.git('ls-remote','--exit-code','--heads','origin',self.ref(source),check=False)
  if p.returncode==2:return 0
  if p.returncode:raise StoreUnavailable('REMOTE_READ_FAILED')
  rows=p.stdout.decode().splitlines()
  if len(rows)!=1:raise StoreUnavailable('REMOTE_REF_AMBIGUOUS')
  sha,ref=rows[0].split()
  if ref!=self.ref(source) or not re.fullmatch('[0-9a-f]{40}',sha):raise StoreUnavailable('REMOTE_REF_INVALID')
  return sha
 def read(self,source):
  revision=self.remote_head(source)
  if revision==0:return 0,None
  self.git('fetch','--no-tags','--no-write-fetch-head','origin',revision)
  raw=self.git('show',revision+':state.json').stdout
  if len(raw)>self.max_bytes:raise StoreUnavailable('STATE_REQUIRES_PAGING')
  value=json.loads(raw)
  if value.get('schema')==SCHEMA:
   try:value=unpack(raw,lambda name:self.git('show',revision+':'+name).stdout,self.page_bytes,self.max_bytes)
   except ValueError as exc:raise StoreUnavailable(str(exc)) from None
  if value.get('source')!=source:raise StoreUnavailable('STATE_SOURCE_MISMATCH')
  return revision,value
 def cas(self,source,revision,state):
  self.ref(source)
  if state.get('source')!=source:raise ValueError('STATE_SOURCE_SCOPE')
  if revision!=0 and not (isinstance(revision,str) and re.fullmatch('[0-9a-f]{40}',revision)):
   raise ValueError('INVALID_REVISION')
  try:files=pack(state,self.page_bytes,self.max_bytes)
  except ValueError as exc:raise StoreUnavailable(str(exc)) from None
  entries=[]
  for name,raw in sorted(files.items()):
   blob=self.git('hash-object','-w','--stdin',data=raw).stdout.decode().strip()
   entries.append(f'100644 blob {blob}\t{name}\n')
  tree=self.git('mktree',data=''.join(entries).encode()).stdout.decode().strip()
  args=['-c','user.name=JARVIS source state','-c','user.email=jarvis-source@users.noreply.github.com','commit-tree',tree]
  if revision:args+=['-p',revision]
  message=('Checkpoint source coordination state '+uuid.uuid4().hex+' [skip ci]\n').encode()
  commit=self.git(*args,data=message).stdout.decode().strip()
  p=self.git('push','origin',commit+':'+self.ref(source),check=False)
  if not p.returncode:return True
  # A competing writer causes a non-fast-forward rejection. Authentication,
  # connection and other failures must stop work rather than look like a retry.
  rejection=p.stderr.decode(errors='replace')
  if ('[rejected]' in rejection or '[remote rejected]' in rejection) and self.remote_head(source)!=revision:return False
  raise StoreUnavailable('DURABLE_PUSH_FAILED')
