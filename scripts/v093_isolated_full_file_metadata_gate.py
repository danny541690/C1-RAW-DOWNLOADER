"""Read-only deep file metadata inventory for 322 months, four source lanes.

Counts every file entry in each source-month folder; no file bytes are read.
File presence, size and naming do not prove numeric or PIT correctness.
"""
import collections
from scripts.v093_standard_r1 import ROOT,SOURCES,ls

FOLDER='application/vnd.google-apps.folder'

def audit_year_range(d,start,end,latest='2026-10'):
    if not (2000<=start<=end<=2026):raise ValueError('INVALID_RANGE')
    years={str(x['name']):x for x in ls(d,ROOT) if x.get('mimeType')==FOLDER}
    result={'start':start,'end':end,'months':{},'certified':0,'read_only':True}
    for year in range(end,start-1,-1):
        yr=str(year)
        parent=years.get(yr)
        sources={x['name']:x for x in ls(d,parent['id']) if x.get('mimeType')==FOLDER} if parent else {}
        for source in SOURCES:
            folder=sources.get(source)
            monthfolders=collections.defaultdict(list)
            if folder:
                for x in ls(d,folder['id']):
                    if x.get('mimeType')==FOLDER:
                        monthfolders[x['name']].append(x)
            for m in range(1,13):
                key=f'{year}-{m:02d}'
                if key>latest:continue
                row=result['months'].setdefault(key,{})
                choices=monthfolders.get(key,[])
                if len(choices)!=1:
                    row[source]={'status':'MISSING_MONTH_FOLDER' if not choices else 'DUPLICATE_MONTH_FOLDER','file_count':0,'zip_count':0,'other_count':0,'zero_size':0,'bytes_total':0}
                    continue
                children=[x for x in ls(d,choices[0]['id']) if x.get('mimeType')!=FOLDER]
                names=collections.Counter(x['name'] for x in children)
                zipfiles=[x for x in children if x['name'].lower().endswith('.zip')]
                zeros=[x for x in children if int(x.get('size',0))<=0]
                dup=[k for k,v in names.items() if v>1]
                row[source]={'status':'FILES_PRESENT_PENDING_QA' if children else 'EMPTY_MONTH_FOLDER','file_count':len(children),'zip_count':len(zipfiles),'other_count':len(children)-len(zipfiles),'zero_size':len(zeros),'duplicate_names':dup[:20],'bytes_total':sum(int(x.get('size',0)) for x in children)}
    return result

def summarize(reports):
    allmonths={}
    for report in reports:
        for month,row in report['months'].items():
            if month in allmonths:raise ValueError('DUPLICATE_MONTH_IN_SHARDS')
            allmonths[month]=row
    expected={f'{y}-{m:02d}' for y in range(2000,2027) for m in range(1,13) if f'{y}-{m:02d}'<='2026-10'}
    if set(allmonths)!=expected:raise ValueError('MISSING_MONTH_SHARDS')
    counts=collections.Counter()
    queue=[]
    for month,rows in sorted(allmonths.items(),reverse=True):
        if set(rows)!=set(SOURCES):raise ValueError('SOURCE_MISMATCH_'+month)
        for source,r in rows.items():
            counts['source_month_pairs']+=1
            counts['files']+=r['file_count']
            counts['zip_files']+=r['zip_count']
            counts['nonzip_files']+=r['other_count']
            counts['bytes_total']+=r['bytes_total']
            counts['zero_size']+=r['zero_size']
            counts['duplicate_names']+=len(r.get('duplicate_names',[]))
            counts[r['status']]+=1
            if r['status']!='FILES_PRESENT_PENDING_QA' or r['zero_size'] or r.get('duplicate_names'):
                queue.append({'month':month,'source':source,'status':r['status'],'zero_size':r['zero_size'],'duplicate_names':r.get('duplicate_names',[]),'action':'VERIFY_FORMAT_AND_BACKFILL_IF_NEEDED'})
    if counts['source_month_pairs']!=1288:raise ValueError('WRONG_SCOPE')
    return {'months':322,'counts':dict(counts),'review_queue':queue,'certified_months':0,'read_only':True}
