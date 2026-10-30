"""Explicit durable-outbox continuation transport; never logs token/response bodies."""
import json,re,urllib.request,urllib.error
class DispatchUnavailable(RuntimeError):pass
class WorkflowDispatch:
 def __init__(self,repository,workflow,ref,token,inputs,open_url=urllib.request.urlopen):
  if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('REPOSITORY')
  if not re.fullmatch(r'jarvis-seven-[A-Za-z0-9_-]+\.yml',workflow):raise ValueError('CONTINUATION_WORKFLOW_SCOPE')
  if ref!='main' and ref!='codex/seven-source-closed-loop-design-20261029':raise ValueError('CONTINUATION_REF_SCOPE')
  if not token or not isinstance(inputs,dict):raise ValueError('DISPATCH_INPUTS')
  self.repo=repository;self.workflow=workflow;self.ref=ref;self.token=token;self.inputs=inputs;self.open_url=open_url
 def __call__(self,identity):
  if not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('DISPATCH_IDENTITY')
  data=json.dumps(dict(ref=self.ref,inputs=dict(self.inputs,continuation_id=identity))).encode()
  req=urllib.request.Request('https://api.github.com/repos/'+self.repo+'/actions/workflows/'+self.workflow+'/dispatches',data=data,method='POST',headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
  try:
   with self.open_url(req,timeout=30) as response:
    if response.status!=204:raise DispatchUnavailable('UNEXPECTED_DISPATCH_STATUS')
  except urllib.error.HTTPError as exc:raise DispatchUnavailable('DISPATCH_HTTP_'+str(exc.code)) from None
  except (OSError,TimeoutError):raise DispatchUnavailable('DISPATCH_TRANSPORT_UNCERTAIN') from None
