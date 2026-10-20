"""One-way RAW capture only: existing months skipped, failed units never retried."""
import argparse,collections,concurrent.futures,datetime as dt,io,json,os,time,zipfile
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_history_reverse import History,key,getj,putj
from scripts.v093_three_year_repair import ROOT,REPORT_ROOT,Audit,listing,stamp,sha
import scripts.v093_three_year_repair as native

RUN='RAW_FIRSTPASS_202612_TO_200001_V1'
MONTHS=[f'{y}-{m:02d}' for y in range(2026,1999,-1) for m in range(12,0,-1)]
SOURCES=('TWSE','TPEx','MOPS','FinMind')

def month_policy(month,today,existing):
    if month>today.strftime('%Y-%m'):return 'FUTURE_MONTH_NOT_AVAILABLE'
    if any(existing.values()):return 'SKIPPED_EXISTING_NO_TOPUP'
    return 'NEW_CAPTURE_CURRENT_MONTH_PARTIAL' if month==today.strftime('%Y-%m') else 'NEW_CAPTURE'

def pack(items):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        receipts=[]
        for receipt,raw in items:
            name=receipt['unit_id']+'.raw';z.writestr(name,raw);receipts.append(dict(receipt,file=name))
        z.writestr('manifest.json',json.dumps({'run':RUN,'units':receipts,'numeric_verified':False,'pit_verified':False}))
    raw=out.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.testzip():raise ValueError('ZIP_CRC_FAILED')
    return raw

class FirstPass(History):
    def __init__(self,minutes):
        self.d=Drive(service());self.control=self.d.folder(REPORT_ROOT,RUN)
        self.checkpoint=getj(self.d,self.control,'CURSOR.json') or {'version':RUN,'month_index':0,'months':{},'done':False}
        if self.checkpoint.get('version')!=RUN or not 0<=self.checkpoint['month_index']<=len(MONTHS):raise ValueError('FIRSTPASS_CURSOR_CONFLICT')
        self.until=time.monotonic()+minutes*60;self.circuit=collections.Counter();self.folders={};self.request_counts=collections.Counter();self.index={};self.alerts=[]
        self.today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    def children(self,parent):
        if parent not in self.index:self.index[parent]=listing(self.d,parent)
        return self.index[parent]
    def existing_folder(self,parent,name):
        found=[f for f in self.children(parent) if f['name']==name and f['mimeType']=='application/vnd.google-apps.folder']
        if len(found)>1:raise ValueError('DUPLICATE_FOLDER '+name)
        return found[0]['id'] if found else None
    def inventory(self,month):
        found={s:[] for s in SOURCES};year=self.existing_folder(ROOT,month[:4])
        if not year:return found
        for source in SOURCES:
            sf=self.existing_folder(year,source);mf=self.existing_folder(sf,month) if sf else None
            if mf:
                found[source]=[{'id':f['id'],'name':f['name'],'bytes':int(f.get('size',0))} for f in self.children(mf)
                               if f['mimeType']!='application/vnd.google-apps.folder' and f['name'].lower().endswith(('.zip','.raw','.json','.jsonl','.csv','.html','.htm','.parquet'))
                               and not any(t in f['name'].lower() for t in ('manifest','receipt','checkpoint','audit','report','metadata'))]
        return found
    def flush(self,results,bucket):
        groups=collections.defaultdict(list);bad=[]
        for j,e,raw in results:
            if raw is not None:
                if e['status']=='SAVED_BASIC_VERIFIED':groups[e['source']].append((e,raw))
                else:bad.append((e,raw))
        for source,items in groups.items():
            raw=pack(items);name=RUN+'_'+bucket+'_'+sha(raw)[:20]+'.zip'
            self.d.put(self.folder(source,self.active),name,raw,'application/zip',overwrite=False)
            self.state['archives'].append({'source':source,'name':name,'sha256':sha(raw),'bytes':len(raw),'remote_readback_verified':True})
        if bad:
            raw=pack(bad);self.d.put(self.d.folder(self.monthctrl,'QUARANTINE'),'quarantine_'+sha(raw)[:20]+'.zip',raw,'application/zip',overwrite=False)
        for j,e,raw in results:
            self.state[bucket][e['unit_id']]=e
            self.state['stocks']=sorted(set(self.state['stocks'])|set(e.get('codes_found',[])))
        self.save_state()
    def process(self,jobs,bucket):
        pending=[j for j in jobs if key(j) not in self.state[bucket]]
        for offset in range(0,len(pending),6):
            if time.monotonic()>=self.until:return False
            batch=pending[offset:offset+6]
            # Durable intent precedes HTTP. Interrupted/failed requests are never replayed.
            for j in batch:self.state[bucket][key(j)]=dict(j,unit_id=key(j),status='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED',attempts=0)
            self.save_state()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda j:self.fetch_one(j,bucket),batch))
            self.flush(results,bucket)
        return True
    def save_report(self,policy,existing=None):
        units=list(self.state.get('units',{}).values())+list(self.state.get('financial_units',{}).values())
        problems=[e for e in units if e.get('status')!='SAVED_BASIC_VERIFIED']
        report={'version':RUN,'month':self.active,'policy':policy,'updated_at':stamp(),'as_of_date':self.today.isoformat(),
                'existing_files':existing,'state_counts':dict(collections.Counter(e['status'] for e in units)),
                'problems':problems,'archives':self.state.get('archives',[]),'repair_enabled':False,'gap_fill_enabled':False,
                'FinMind':'NOT_REQUESTED_GAP_SUPPLEMENT_DISABLED','full_market_complete':False,'numeric_verified':False,'pit_verified':False}
        putj(self.d,self.monthctrl,'RESULT.json',report)
        if problems or policy=='INVENTORY_ERROR_NO_FETCH':
            alert={'month':self.active,'problem_count':len(problems),'policy':policy,'report_folder_id':self.monthctrl}
            self.alerts.append(alert);print('FIRSTPASS_ALERT '+json.dumps(alert),flush=True)
        return report
    def progress(self):
        entries=self.checkpoint['months']
        out={'version':RUN,'updated_at':stamp(),'total_months':len(MONTHS),'processed_months':self.checkpoint['month_index'],
             'next_month':MONTHS[self.checkpoint['month_index']] if self.checkpoint['month_index']<len(MONTHS) else None,
             'month_status_counts':dict(collections.Counter(e['policy'] for e in entries.values())),
             'problem_months':[m for m,e in entries.items() if e.get('problem_count',0)],'repair_enabled':False,'gap_fill_enabled':False,'done':self.checkpoint['done']}
        putj(self.d,self.control,'PROGRESS.json',out);return out
    def run(self):
        putj(self.d,self.control,'PLAN.json',{'version':RUN,'months':MONTHS,'order':'STRICT_DESCENDING','existing_month_policy':'SKIP_WHOLE_MONTH_DO_NOT_TOP_UP','sources_primary':['TWSE','TPEx','MOPS'],'FinMind':'GAP_FILL_DISABLED','repair_enabled':False,'gap_fill_enabled':False,'future_months':'RECORD_NOT_AVAILABLE_NO_REQUEST','partial_current_month':'ONLY_THROUGH_AS_OF_DATE_NO_LATER_TOPUP','interrupted_request':'RECORD_UNKNOWN_NEVER_RETRY'})
        native.TODAY=self.today
        while self.checkpoint['month_index']<len(MONTHS) and time.monotonic()<self.until:
            month=MONTHS[self.checkpoint['month_index']];self.active=month;self.monthctrl=self.d.folder(self.control,month)
            saved=getj(self.d,self.monthctrl,'MONTH_STATE.json')
            self.state=saved or {'month':month,'units':{},'financial_units':{},'stocks':[],'market_codes':{},'archives':[],'phase':'OFFICIAL_CORE'}
            try:
                existing={} if saved else ({} if month>self.today.strftime('%Y-%m') else self.inventory(month))
                policy=saved.get('policy') if saved else month_policy(month,self.today,existing)
            except Exception as exc:
                policy='INVENTORY_ERROR_NO_FETCH';existing={'error':type(exc).__name__+':'+str(exc)[:180]}
                self.state['units']['inventory']={'status':'INVENTORY_ERROR_NO_FETCH','error':existing['error']}
            self.state['policy']=policy;self.save_state()
            if policy.startswith('NEW_CAPTURE'):
                # No holiday retry, no cross-source fallback, no FinMind gap tasks.
                core=Audit.jobs(object.__new__(Audit),month,set())
                if not self.process(core,'units'):
                    self.save_report(policy);break
                if not self.process(self.financial_jobs(),'financial_units'):
                    self.save_report(policy);break
            report=self.save_report(policy,existing)
            self.checkpoint['months'][month]={'policy':policy,'problem_count':len(report['problems']),'report_folder_id':self.monthctrl,'finished_utc':stamp()}
            self.checkpoint['month_index']+=1;self.checkpoint['done']=self.checkpoint['month_index']==len(MONTHS)
            self.save_cursor();self.progress()
            print('FIRSTPASS_MONTH '+json.dumps({'month':month,'policy':policy,'problem_count':len(report['problems'])}),flush=True)
        progress=self.progress()
        print('FIRSTPASS_BATCH_SUMMARY '+json.dumps({'progress':progress,'alerts':self.alerts}),flush=True)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps({'progress':progress,'alerts':self.alerts},ensure_ascii=False,indent=2)+'\n```\n')
        if progress['done']:
            # Disable only this replacement workflow, not any other task.
            import urllib.request
            req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/workflows/v093-raw-firstpass.yml/disable',data=b'',method='PUT',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(req,timeout=20):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=40);a=p.parse_args();FirstPass(a.minutes).run()
