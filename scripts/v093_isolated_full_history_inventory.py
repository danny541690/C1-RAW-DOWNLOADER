"""Read-only 2000-2026 Drive folder-level inventory, without false certification.

Lists each year/source folder once; reports month-folder presence only.
Does not inspect each month's files or infer ZIP completeness.
"""
import json
from scripts.v093_standard_r1 import ROOT,SOURCES,ls

def inventory(d,start_year,end_year,latest_month='2026-10'):
    if not (2000<=start_year<=end_year<=2026):
        raise ValueError('INVALID_YEAR_RANGE')
    root=ls(d,ROOT)
    result={'start_year':start_year,'end_year':end_year,'latest_month':latest_month,'months':{},'source_month_folder_present':0,'source_month_folder_missing':0,'source_month_folder_ambiguous':0,'certified_months':0,'read_only':True}
    for year in range(end_year,start_year-1,-1):
        yr=str(year)
        year_folders=[x for x in root if x.get('name')==yr and x.get('mimeType')=='application/vnd.google-apps.folder']
        sources={}
        if len(year_folders)==1:
            source_folders=ls(d,year_folders[0]['id'])
            for source in SOURCES:
                found=[x for x in source_folders if x.get('name')==source and x.get('mimeType')=='application/vnd.google-apps.folder']
                if len(found)==1:
                    contents=ls(d,found[0]['id'])
                    source_months={}
                    for x in contents:
                        if x.get('mimeType')=='application/vnd.google-apps.folder':
                            source_months[x.get('name')]=source_months.get(x.get('name'),0)+1
                    sources[source]=source_months
                else:
                    sources[source]=None if not found else {'_AMBIGUOUS':len(found)}
        for month in range(12,0,-1):
            key=f'{year}-{month:02d}'
            if key>latest_month:continue
            states={}
            for source in SOURCES:
                if len(year_folders)!=1:
                    state='YEAR_FOLDER_MISSING' if not year_folders else 'YEAR_FOLDER_AMBIGUOUS'
                elif sources[source] is None:
                    state='SOURCE_FOLDER_MISSING'
                elif '_AMBIGUOUS' in sources[source]:
                    state='SOURCE_FOLDER_AMBIGUOUS'
                else:
                    count=sources[source].get(key,0)
                    state='MONTH_FOLDER_PRESENT_UNVERIFIED' if count==1 else ('MONTH_FOLDER_MISSING' if count==0 else 'MONTH_FOLDER_AMBIGUOUS')
                states[source]=state
                if state=='MONTH_FOLDER_PRESENT_UNVERIFIED':result['source_month_folder_present']+=1
                elif 'AMBIGUOUS' in state:result['source_month_folder_ambiguous']+=1
                else:result['source_month_folder_missing']+=1
            result['months'][key]=states
    result['month_count']=len(result['months'])
    result['source_month_total']=len(result['months'])*len(SOURCES)
    assert result['source_month_total']==result['source_month_folder_present']+result['source_month_folder_missing']+result['source_month_folder_ambiguous']
    return result
