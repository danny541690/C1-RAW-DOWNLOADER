"""Reuse compiled snapshots and extend only the two failed oldest-side probes."""
import json
from pathlib import Path
from scripts.v093_admission_runtime import Catalog
from scripts.v093_source_git_store import GitCAS

def main():
 folder=Path('collected/catalogs');cases=json.loads((folder/'slot-cases.json').read_text());catalogs=json.loads((folder/'candidate-catalogs.json').read_text())['catalogs']
 for source in ('TWSE','TPEx'):
  entry=catalogs[source]['ASC'];catalog=Catalog(GitCAS(Path.cwd(),'jarvis-source-preflight/recovery-reader'),entry,source,'ASC');last=catalog.page(len(catalog.index['pages'])-1)[-1][1]
  if last['definition']['key']==cases[source+'|ASC'][0]['definition']['key']:raise ValueError('POSITIVE_SECOND_CASE_MUST_BE_DISTINCT')
  cases[source+'|ASC'].append(last)
 out=Path('results');out.mkdir(exist_ok=True);(out/'slot-cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
