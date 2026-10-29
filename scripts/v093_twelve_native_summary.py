import json,os
from pathlib import Path
from scripts.v093_source_partition import COUNTS
from scripts.v093_source_git_store import GitCAS

def main():
 root=Path('collected');out=Path('results');out.mkdir(exist_ok=True);reports=[json.loads(p.read_text()) for p in root.rglob('slot.json')];expected={(s,slot) for s,n in COUNTS.items() for slot in (('ASC','DESC') if n==2 else ('DESC',))}
 needs=json.loads(os.environ['BATCH_NEEDS']);namespace='twelve-native-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT'];cold={}
 for source in COUNTS:
  _,state=GitCAS(Path.cwd(),'jarvis-source-preflight/'+namespace).read(source);cold[source]=state.get('admission',{}) if state else None
 def find(name):
  ps=list(root.rglob(name));return json.loads(ps[0].read_text()) if ps else None
 result=dict(schema='JARVIS_TWELVE_NATIVE_MERGED_HANDOFF_V1',jobs={k:v['result'] for k,v in needs.items()},slots=reports,source_cold_cursors=cold,catalogs=find('candidate-catalogs.json'),old_writer_audit=find('old-writer-audit.json'),offline=find('full-repo-summary.json'),source_requests=0,formal_raw_writes=0,formal_data_repaired=0,production_activation=False,full_acceptance=False,quota_fixture_policy=dict(limit=1,window=3600,spacing=0),quota_fixture_only=True)
 present={(r['source'],r['slot']) for r in reports};wins=sum(r.get('quota_result')=='WIN' for r in reports);deferred=sum(r.get('quota_result')=='DEFER' for r in reports)
 cold_ok=all(cold.get(r['source']) and cold[r['source']].get(r['slot'],{}).get('finished') is True and cold[r['source']][r['slot']].get('archived_status_counts',{}).get('RAW_BASIC_VERIFIED',0)==r['case_count'] for r in reports)
 result['passed']=cold_ok and all(v=='success' for v in result['jobs'].values()) and present==expected and len(reports)==12 and all(r['passed'] for r in reports) and (wins,deferred)==(7,5)
 result.update(quota_winners=wins,quota_deferred=deferred,real_units_verified=sum(r['case_count'] for r in reports if r['passed']))
 result['remaining_release_work']=['Approve execution scope and generate missing/correction contracts for held task types','Verify provider-facing twelve-worker long-run limits and throughput; control fixture is not that load test','Merge pinned release, activate recovery controller and validate first formal batch']
 (out/'twelve-native-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],slots=len(reports),real_units_verified=result['real_units_verified'],quota_winners=wins,quota_deferred=deferred,production_activation=False)),flush=True)
 if not result['passed']:raise ValueError('TWELVE_REAL_NATIVE_HANDOFF_INCOMPLETE')
if __name__=='__main__':main()
