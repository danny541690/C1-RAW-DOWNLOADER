"""September v0.95 single-entry controller. Workflow success is NOT data or PIT certification."""
import base64, datetime as dt, json, os, time, urllib.error, urllib.parse, urllib.request
REPO='danny541690/C1-RAW-DOWNLOADER'
BASE='https://api.github.com/repos/'+REPO
STATE='governance/v095/runtime/202609_autopilot_state.json'
PHASES={
 'bronze':['v095-202609-real-drive-byte-audit.yml','v095-202609-bronze-admission.yml','v095-202609-tpex-official-gap-recheck.yml','v095-202609-seven-source-audit-bundle.yml'],
 'silver':['v095-202609-silver-price-conversion.yml','v095-202609-multi-silver-four-lane.yml','v095-202609-typed-silver-gate.yml','v095-202609-silver-mops-revenue.yml','v095-202609-silver-tdcc-conversion.yml','v095-202609-silver-taifex-ndc-four-lane.yml','v095-september-silver-scoped-release.yml'],
 'gold':['v095-202609-gold-descriptive-two-lane.yml','v095-202609-gold-three-subsets.yml','v095-202609-gold-valuation-foreign.yml','v095-202609-tdcc-gold-weekly.yml','v095-twse-credit-three-layer.yml']}
def api(method,path,data=None):
    req=urllib.request.Request(BASE+path,method=method,
      data=json.dumps(data).encode() if data is not None else None,
      headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        b=r.read()
        return json.loads(b) if b else {}
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def load():
    try:
        x=api('GET','/contents/'+STATE)
        return json.loads(base64.b64decode(x['content'])),x['sha']
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        return {'schema':'JARVIS_SEPT2026_AUTOPILOT_V1','month':'2026-09','phase':'bronze','steps':{},'created_utc':utc(),'production_approved':False,'pit_certified':False},None
def save(s,sha):
    s.update(updated_utc=utc(),production_approved=False,pit_certified=False)
    d={'branch':'main','message':'checkpoint(v095): September autopilot','content':base64.b64encode((json.dumps(s,ensure_ascii=False,indent=2)+'\n').encode()).decode()}
    if sha:d['sha']=sha
    return api('PUT','/contents/'+STATE,d)['content']['sha']
def refresh(w,e):
    if not e.get('run_id'):
        q='/actions/workflows/'+urllib.parse.quote(w,safe='')+'/runs?per_page=30&event=workflow_dispatch'
        cutoff=dt.datetime.fromisoformat(e['sent'])-dt.timedelta(seconds=90)
        for r in api('GET',q).get('workflow_runs',[]):
            at=dt.datetime.fromisoformat(r['created_at'].replace('Z','+00:00'))
            if at>=cutoff and r['id'] not in set(e.get('prior_ids',[])):
                e.update(run_id=r['id'],url=r['html_url']);break
        if not e.get('run_id'):return
    r=api('GET','/actions/runs/'+str(e['run_id']))
    e['status']='success' if r.get('conclusion')=='success' else 'failure' if r.get('status')=='completed' else 'running'
    e['conclusion']=r.get('conclusion')
def phase_run(s,sha,phase):
    names=PHASES[phase]
    for w in names:
        e=s['steps'].setdefault(w,{'status':'new','attempts':0})
        if e['status'] in ('new','failure') and e['attempts']<2:
            prior=[e['run_id']] if e.get('run_id') else []
            api('POST','/actions/workflows/'+urllib.parse.quote(w,safe='')+'/dispatches',{'ref':'main'})
            e.update(status='sent',attempts=e['attempts']+1,sent=utc(),prior_ids=prior)
            e.pop('run_id',None)
            sha=save(s,sha)
            print('DISPATCH',phase,w,e['attempts'],flush=True)
    end=time.monotonic()+int(os.getenv('POLL_BUDGET_SECONDS','2700'))
    while time.monotonic()<end:
        active=False
        for w in names:
            e=s['steps'][w]
            if e['status'] in ('sent','running'):
                refresh(w,e)
                sha=save(s,sha)
            active|=e['status'] in ('sent','running')
        if not active:break
        time.sleep(30)
    if all(s['steps'][w]['status']=='success' for w in names):
        s['phase']={'bronze':'silver','silver':'gold','gold':'pit'}[phase]
    elif any(s['steps'][w]['status']=='failure' and s['steps'][w]['attempts']>=2 for w in names):
        s['phase']='blocked_'+phase
        s['blocking_workflows']=[w for w in names if s['steps'][w]['status']=='failure']
    else:s['phase']=phase
    return save(s,sha)
def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise RuntimeError('WRONG_REPOSITORY')
    s,sha=load()
    # Continue immediately to the next dependency phase if the prior phase has finished.
    # Never label the controller's run as complete while there is queued work.
    for phase in ('bronze','silver','gold'):
        if s['phase'] == phase:
            sha=phase_run(s,sha,phase)
            if s['phase'] == phase or s['phase'].startswith('blocked_'):
                break
    if s['phase']=='pit':
        s.update(phase='blocked_pit',pit_gate='UNVERIFIED_PUBLICATION_TIMESTAMPS_AND_443_FORMULA_DEPENDENCIES',full_443_certified=False)
        sha=save(s,sha)
    print(json.dumps({'phase':s['phase'],'statuses':{k:v['status'] for k,v in s['steps'].items()},'production_approved':False,'pit_certified':False},ensure_ascii=False),flush=True)
    if s['phase'].startswith('blocked_'):raise SystemExit(2)
if __name__=='__main__':main()
