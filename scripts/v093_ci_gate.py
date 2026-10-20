"""Reuse one successful offline suite for identical executable inputs.

This gate approves code execution only, never source data or a production release.
"""
import hashlib,json,os,urllib.request


def execution_signature(tree):
    if tree.get('truncated'):raise ValueError('TRUNCATED_EXECUTION_TREE')
    inputs=sorted((f['path'],f['sha'],f['mode']) for f in tree['tree']
                  if f['type']=='blob' and (f['path'].startswith(('scripts/','tests/','.github/workflows/')) or f['path']=='requirements-qa.lock'))
    if not inputs:raise ValueError('EMPTY_EXECUTION_INPUTS')
    return hashlib.sha256(json.dumps(inputs,separators=(',',':')).encode()).hexdigest()


def approved_code(get,head,branch='main'):
    runs=get('/actions/workflows/v093-offline-tests.yml/runs?status=success&branch='+branch+'&per_page=20')['workflow_runs']
    eligible=[r for r in runs if r.get('status')=='completed' and r.get('conclusion')=='success' and r.get('head_branch')==branch]
    for run in eligible:
        if run['head_sha']==head:return {'ready':True,'reason':'EXACT_COMMIT_TESTED','test_run_id':run['id']}
    signatures={}
    def signature(commit):
        if commit not in signatures:
            sha=get('/git/commits/'+commit)['tree']['sha']
            signatures[commit]=execution_signature(get('/git/trees/'+sha+'?recursive=1'))
        return signatures[commit]
    for run in eligible[:5]:
        if signature(head)==signature(run['head_sha']):
            return {'ready':True,'reason':'IDENTICAL_EXECUTION_INPUTS_TESTED','test_run_id':run['id']}
    return {'ready':False,'reason':'WAITING_FOR_SINGLE_OFFLINE_ACCEPTANCE'}


def main():
    token=os.environ['GITHUB_TOKEN'];repo=os.environ['GITHUB_REPOSITORY']
    def get(path):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    try:result=approved_code(get,os.environ['GITHUB_SHA'],os.environ.get('GITHUB_REF_NAME','main'))
    except Exception as exc:result={'ready':False,'reason':'CODE_EVIDENCE_READ_FAILED','error':type(exc).__name__}
    print(json.dumps(result),flush=True)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('ready='+str(result['ready']).lower()+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('程式版本驗證：'+result['reason']+'；僅供排程執行，不代表資料核准。\n')

if __name__=='__main__':main()
