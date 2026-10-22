"""One-time authorized cleanup deployment handoff; preserve all primary cursors."""
import json
import os
import re
import time
import urllib.request

from scripts.v093_five_stage_durable_gate import _read, commit
from scripts.v093_stage06_ledger import digest


def main():
    repo,token=os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN']
    keep=os.environ['CLEANUP_DEPLOY_COMMIT']
    prefix='https://api.github.com/repos/'+repo
    lease_url=prefix+'/contents/.github/live-state/five-stage-leases.json'
    allowed={'.github/workflows/v093-v2-'+suffix+'.yml' for suffix in (
        '01-raw','02-qa','03-price','04-financial','05-chip','06-reconcile-repair')}
    def api(method,path):
        request=urllib.request.Request(prefix+path,method=method,headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            raw=response.read();return json.loads(raw) if raw else {}
    _,state=_read(lease_url,token)
    cancelled={}
    for pool,item in state['jobs'].items():
        lease=item.get('lease') or {}
        match=re.fullmatch(r'([0-9]+)/(RAW|QA1|PRICE|FINANCIAL|CHIP|RECONCILE)',lease.get('owner',''))
        if not match:continue
        run=match[1]
        record=api('GET','/actions/runs/'+run)
        if record.get('head_sha')==keep:continue
        if record.get('path') not in allowed:
            print('HANDOFF_SKIP_UNKNOWN_WORKFLOW '+run,flush=True);continue
        if record['status']!='completed' and run not in cancelled:
            api('POST','/actions/runs/'+run+'/cancel')
            cancelled[run]=True
        for _ in range(60):
            record=api('GET','/actions/runs/'+run)
            if record['status']=='completed':break
            time.sleep(5)
        if record['status']!='completed':
            print('HANDOFF_WAIT_TERMINAL_KEEP_LEASE '+run,flush=True);continue
        _,latest=_read(lease_url,token)
        current=latest.get('jobs',{}).get(pool,{}).get('lease') or {}
        if current==lease:
            commit(lease_url,token,pool,lease['owner'],lease['fence'],
                   digest(dict(reason='USER_AUTHORIZED_STAGE06_CLEANUP_HANDOFF',old_run=run)))
        print('HANDOFF_TERMINAL_CONFIRMED '+run+' '+pool,flush=True)


if __name__=='__main__':main()
