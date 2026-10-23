"""Stage 07: official NDC business indicators, immutable RAW and monthly references.
No original-vintage/PIT claim is made for today's revised historical series.
"""
import argparse, collections, csv, datetime as dt, hashlib, html, io, json
import math, posixpath, re, time, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
ROOT='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'
REPORT='1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
ZIP_URL='https://ws.ndc.gov.tw/Download.ashx?icon=.zip&n=5pmv5rCj5oyH5qiZ5Y%2BK54eI6JmfLnppcA%3D%3D&u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkyL2VhMjM1YmQ5LWQwNTItNGE2OS1hYmZjLWQ1Yzc4NWQzZDBlMi56aXA%3D'
LIST_URL='https://www.ndc.gov.tw/news9_1.aspx?n=257d28e6c2dcc0f8&sms=ec9205f763e2a607'
NEWS_URL='https://www.ndc.gov.tw/nc_332_40495'
XLSX_URL='https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx'
FLOOR='2000-01'
TZ=dt.timezone(dt.timedelta(hours=8))
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def month(value,excel=False):
    if value is None:return None
    text=str(value).strip()
    if excel:
        try:
            number=float(text)
            if 10000<=number<=80000:return (dt.date(1899,12,30)+dt.timedelta(days=number)).strftime('%Y-%m')
        except (ValueError,OverflowError):pass
    if re.fullmatch(r'\d{5,6}',text):
        y,m=int(text[:-2]),int(text[-2:]);y=y+1911 if y<1911 else y
        try:return dt.date(y,m,1).strftime('%Y-%m')
        except ValueError:return None
    match=re.fullmatch(r'(\d{3,4})(?:[-/年.]?)(\d{2}|\d)(?:[-/月.](?:\d{1,2})日?)?(?:月)?(?:T.*| 00:00:00)?',text)
    if not match:return None
    y,m=int(match[1]),int(match[2]);y=y+1911 if y<1911 else y
    try:return dt.date(y,m,1).strftime('%Y-%m')
    except ValueError:return None
def months_desc(upper):
    y,m=map(int,upper.split('-'));out=[]
    while (y,m)>=(2000,1):
        out.append(f'{y:04d}-{m:02d}');m-=1
        if not m:y-=1;m=12
    return out
def bounded_zip(raw):
    z=zipfile.ZipFile(io.BytesIO(raw))
    if len(z.infolist())>300 or sum(x.file_size for x in z.infolist())>100_000_000:raise ValueError('ZIP_EXPANSION_LIMIT')
    if any(x.flag_bits&1 or x.file_size>40_000_000 for x in z.infolist()):raise ValueError('ZIP_MEMBER_LIMIT')
    bad=z.testzip()
    if bad:raise ValueError('ZIP_CRC_FAILED:'+bad)
    return z
def table(name,rows,excel=False):
    header=None;out={};row_numbers={}
    for number,row in enumerate(rows,1):
        if header is None:
            if row and str(row[0]).strip().lower() in ('date','日期','年月','年月別','資料日期'):
                last=max((i for i,v in enumerate(row) if v not in (None,'')),default=0)
                header=[str(v or '') for v in row[:last+1]]
            continue
        date=month(row[0],excel) if row else None
        if not date:continue
        if date in out:raise ValueError('DUPLICATE_MONTH:'+name+':'+date)
        values=list(row[:len(header)])+[None]*max(0,len(header)-len(row))
        if any(isinstance(v,float) and not math.isfinite(v) for v in values):raise ValueError('NONFINITE_CELL')
        out[date]=values;row_numbers[date]=number
    if not header or len(header)<2 or not out:raise ValueError('DATE_TABLE_NOT_FOUND:'+name)
    return dict(name=name,header=header,rows=out,row_numbers=row_numbers)
def xlsx_tables(raw,prefix=''):
    z=bounded_zip(raw)
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        for node in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS):
            shared.append(''.join(node.itertext()))
    relationships={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    book=ET.fromstring(z.read('xl/workbook.xml'))
    if book.find('s:workbookPr',NS) is not None and book.find('s:workbookPr',NS).get('date1904') in ('1','true'):
        raise ValueError('UNSUPPORTED_EXCEL_1904_DATE_SYSTEM')
    out=[]
    for sheet in book.findall('s:sheets/s:sheet',NS):
        rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target=relationships[rid]
        path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        if not path.startswith('xl/worksheets/'):raise ValueError('XLSX_UNEXPECTED_SHEET_PATH')
        rows=[]
        for node in ET.fromstring(z.read(path)).findall('s:sheetData/s:row',NS):
            cells={}
            for c in node.findall('s:c',NS):
                ref=c.get('r','');letters=re.match('[A-Z]+',ref)
                if not letters:raise ValueError('CELL_REFERENCE_MISSING')
                index=0
                for letter in letters[0]:index=index*26+ord(letter)-64
                value=c.find('s:v',NS);text=value.text if value is not None else None
                if c.get('t')=='s':text=shared[int(text)] if text is not None else None
                elif c.get('t')=='inlineStr':text=''.join(c.find('s:is',NS).itertext())
                elif c.get('t')=='e':raise ValueError('EXCEL_CELL_ERROR')
                cells[index-1]=text
            if cells:rows.append([cells.get(i) for i in range(max(cells)+1)])
        out.append(table(prefix+sheet.attrib['name'],rows,excel=True))
    return out
def parse_bundle(raw):
    z=bounded_zip(raw)
    if 'xl/workbook.xml' in z.namelist():out=xlsx_tables(raw)
    else:
        out=[]
        for path in z.namelist():
            if posixpath.basename(path).lower()=='manifest.csv':continue
            if path.lower().endswith('.xlsx'):out.extend(xlsx_tables(z.read(path),path+'::'))
            elif path.lower().endswith('.csv'):
                b=z.read(path)
                for enc in ('utf-8-sig','cp950'):
                    try:text=b.decode(enc);break
                    except UnicodeDecodeError:pass
                else:raise ValueError('CSV_ENCODING')
                out.append(table(path,list(csv.reader(io.StringIO(text)))))
    if not out:raise ValueError('NO_SUPPORTED_CSV_OR_XLSX_TABLES')
    if not any(any('領先指標' in h for h in t['header']) for t in out):raise ValueError('NDC_INDICATOR_SCHEMA_NOT_FOUND')
    return out
def availability(tables):
    series=[]
    for t in tables:
        for i,name in enumerate(t['header'][1:],1):
            if not name:continue
            dates=sorted(k for k,row in t['rows'].items() if row[i] not in (None,'','-','--','…','...'))
            series.append(dict(table=t['name'],field=name,first=dates[0] if dates else None,last=dates[-1] if dates else None))
    dates=[d for t in tables for d in t['rows']]
    return dict(earliest=min(dates),latest=max(dates),series=series,frequency='MONTHLY',
        requested_floor=FLOOR,retention='ACTUAL_FILE_RANGE_NO_ROLLING_LIMIT_ASSUMED',
        pit_verified=False,historical_values='CURRENT_PUBLISHED_VINTAGE_MAY_BE_REVISED')
def month_payload(tables,period,source):
    out=[];gaps=[];starts=availability(tables)['series']
    for t in tables:
        row=t['rows'].get(period)
        if row is None:
            gaps.append(dict(table=t['name'],status='MONTH_NOT_PRESENT_IN_SOURCE'))
            continue
        cells=[]
        for i,h in enumerate(t['header'][1:],1):
            if not h:continue
            first=next((s['first'] for s in starts if s['table']==t['name'] and s['field']==h),None)
            v=row[i]
            status='VALUE_PRESENT'
            if v in (None,'','-','--','…','...'):
                status='BEFORE_SERIES_START' if first and period<first else 'SOURCE_MISSING_VALUE'
                gaps.append(dict(table=t['name'],field=h,status=status))
            cells.append(dict(field=h,native_value=v,status=status))
        out.append(dict(table=t['name'],source_row=t['row_numbers'][period],source_date_cell=row[0],cells=cells))
    if not out:raise ValueError('MONTH_NOT_PRESENT_IN_SOURCE')
    return dict(source='NDC',month=period,source_archive=source,tables=out,gaps=gaps,
        representation='EXTRACTED_NATIVE_CELL_TEXT_WITH_SOURCE_ARCHIVE_REFERENCE',
        units='AS_PUBLISHED_NO_CONVERSION',numeric_verified=False,pit_verified=False,coverage_certified=False)
class Worker:
    def __init__(self,minutes):
        from scripts.annual_actual_firstpass import Drive,service
        self.d=Drive(service());self.d.direct_readback=True
        self.ctrl=self.d.folder(REPORT,'NDC_INDEPENDENT_STAGE07')
        self.archives=self.d.folder(self.ctrl,'SOURCE_ARCHIVES')
        raw=self.d.read(self.ctrl,'CURSOR.json')
        self.state=json.loads(raw) if raw else dict(revision='NDC_INDEPENDENT_V1',receipts={},archives={},cursor_month='2026-10')
        self.until=time.monotonic()+minutes*60;self.requests=0;self.saved=0
        self.today=dt.datetime.now(TZ).date();self.owner='NDC:'+str(__import__('os').environ.get('GITHUB_RUN_ID','local'))
    def live(self):return time.monotonic()+30<self.until
    def save(self):
        self.state.update(updated_utc=stamp(),source='NDC',run_id=self.owner,coverage_certified=False,numeric_verified=False,pit_verified=False)
        self.d.put(self.ctrl,'CURSOR.json',encode(self.state),'application/json',overwrite=True)
        counts=collections.Counter(v.get('status') for v in self.state['receipts'].values())
        report={k:v for k,v in self.state.items() if k not in ('receipts','archives')}
        report.update(month_status_counts=dict(counts),saved_this_run=self.saved,source_requests_this_run=self.requests,
            saved_months=sum(v.get('status')=='SAVED_RAW_ROWS_READBACK_VERIFIED' for v in self.state['receipts'].values()))
        self.d.put(self.ctrl,'STATUS.json',encode(report),'application/json',overwrite=True)
    def request(self,url):
        allowed=('www.ndc.gov.tw','ws.ndc.gov.tw')
        if urllib.parse.urlparse(url).hostname not in allowed:raise ValueError('NON_OFFICIAL_SOURCE')
        self.requests+=1
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 JARVIS-NDC/1.0','Accept':'*/*'})
        with urllib.request.urlopen(req,timeout=30) as r:
            if urllib.parse.urlparse(r.geturl()).hostname not in allowed:raise ValueError('NON_OFFICIAL_REDIRECT')
            raw=r.read(40_000_001)
        if len(raw)>40_000_000:raise ValueError('SOURCE_SIZE_LIMIT')
        return raw
    def discover(self):
        source=self.state.get('selected_archive')
        if source and self.state.get('checked_epoch',0)>time.time()-21600:
            raw=self.d.read(self.archives,source['name'])
            if raw is None or sha(raw)!=source['sha256']:raise ValueError('ARCHIVE_READBACK_MISMATCH')
            return parse_bundle(raw),source
        candidates=[ZIP_URL,XLSX_URL]
        article=NEWS_URL
        try:
            listing=self.request(LIST_URL)
            links=re.findall(r'href=["\']([^"\']*nc_332_\d+[^"\']*)["\']',listing.decode('utf-8-sig'),re.I)
            if links:article=urllib.parse.urljoin(LIST_URL,html.unescape(links[0]))
            self.state['latest_article_url']=article
        except Exception as exc:self.state['listing_discovery_error']=type(exc).__name__+':'+str(exc)[:160]
        try:
            page=self.request(article);self.d.put(self.archives,'NEWS_'+sha(page)+'.html',page,'text/html',overwrite=False)
            links=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',page.decode('utf-8-sig'))]
            candidates.extend(urllib.parse.urljoin(article,x) for x in links if 'Download.ashx' in x and '.xlsx' in x.lower())
        except Exception as exc:self.state['news_discovery_error']=type(exc).__name__+':'+str(exc)[:160]
        valid=[];errors=[]
        for url in dict.fromkeys(candidates):
            if not self.live():break
            try:
                raw=self.request(url);tables=parse_bundle(raw);bounds=availability(tables)
                name='NDC_'+sha(raw)+('.xlsx' if 'icon=.xlsx' in url.lower() else '.zip')
                self.d.put(self.archives,name,raw,overwrite=False);f=self.d.find(self.archives,name)
                evidence=dict(name=name,file_id=f['id'],sha256=sha(raw),bytes=len(raw),url=url,captured_utc=stamp(),
                    remote_readback_hash_verified=True,zip_crc_verified=True)
                self.state['archives'][evidence['sha256']]=evidence
                valid.append((bounds['latest'],sum(len(t['rows']) for t in tables),tables,evidence))
            except Exception as exc:errors.append(dict(url=url,error=type(exc).__name__+':'+str(exc)[:220]))
        self.state['discovery_errors']=errors
        if not valid:
            if source:
                raw=self.d.read(self.archives,source['name'])
                if raw is not None and sha(raw)==source['sha256']:
                    self.state['using_last_verified_archive']=True
                    return parse_bundle(raw),source
            raise ValueError('NO_VALID_OFFICIAL_BUNDLE:'+json.dumps(errors,ensure_ascii=False))
        _,_,tables,source=max(valid,key=lambda x:(x[0],x[1]))
        self.state.update(selected_archive=source,checked_epoch=time.time(),availability=availability(tables),using_last_verified_archive=False)
        self.save()
        print('NDC_AVAILABILITY '+json.dumps(self.state['availability'],ensure_ascii=False),flush=True)
        return tables,source
    def run(self):
        try:
            tables,source=self.discover();latest=self.state['availability']['latest']
            upper=min(self.today.strftime('%Y-%m'),'2026-10')
            for period in months_desc(upper):
                if not self.live():break
                self.state['cursor_month']=period
                old=self.state['receipts'].get(period,{})
                if old.get('status')=='SAVED_RAW_ROWS_READBACK_VERIFIED':continue
                if period>latest:
                    self.state['receipts'][period]=dict(status='NOT_YET_PUBLISHED_IN_VERIFIED_SOURCE',source_latest=latest)
                    continue
                if not any(period in t['rows'] for t in tables):
                    self.state['receipts'][period]=dict(status='MONTH_NOT_PRESENT_IN_VERIFIED_SOURCE',source_sha256=source['sha256'])
                    continue
                if old.get('attempts',0)>=3:continue
                entry=dict(old,status='PROCESSING',attempts=old.get('attempts',0)+1)
                self.state['receipts'][period]=entry;self.save()
                try:
                    payload=month_payload(tables,period,source);raw=encode(payload)
                    parent=self.d.folder(self.d.folder(self.d.folder(ROOT,period[:4]),'NDC'),period)
                    name='NDC_SOURCE_ROWS_'+sha(raw)+'.json'
                    self.d.put(parent,name,raw,'application/json',overwrite=False);f=self.d.find(parent,name)
                    entry.update(status='SAVED_RAW_ROWS_READBACK_VERIFIED',file_id=f['id'],sha256=sha(raw),
                        source_sha256=source['sha256'],tables=len(payload['tables']),open_items=len(payload['gaps']),
                        remote_readback_hash_verified=True,source_archive_preserved=True,captured_utc=stamp(),
                        numeric_verified=False,pit_verified=False)
                    self.saved+=1
                except Exception as exc:entry.update(status='UNRESOLVED',error=type(exc).__name__+':'+str(exc)[:240])
                self.save()
                print('NDC_MONTH '+json.dumps(dict(month=period,**entry),ensure_ascii=False),flush=True)
            self.state['status']='BACKFILL_RANGE_SAVED_WITH_OPEN_ITEMS' if all(self.state['receipts'].get(m,{}).get('status')=='SAVED_RAW_ROWS_READBACK_VERIFIED'
                for m in months_desc(min(latest,upper))) else 'CHECKPOINTED_CONTINUE_NEXT_WAKE'
            self.save()
        except Exception as exc:
            self.state.update(status='UNRESOLVED_SOURCE_OR_PARSER_ERROR',last_error=type(exc).__name__+':'+str(exc)[:500])
            self.save()
            raise
def main():
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=45);args=p.parse_args()
    if not 1<=args.minutes<=50:raise ValueError('INVALID_RUNTIME')
    Worker(args.minutes).run()
if __name__=='__main__':main()
