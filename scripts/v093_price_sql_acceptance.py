"""Read-only real-archive price formula acceptance against SQLite windows.

No network, Drive writes or release approval. The archive is a bounded sample;
this verifies formula behavior, not market coverage or historical source truth.
"""
import argparse,collections,decimal,hashlib,json,sqlite3,zipfile
from pathlib import Path
from scripts.v093_standard_r4 import parse_member,PARSER_REVISION
from scripts.v093_feature_warmup import warmup_rows


def verify(path,period):
    points=[];excluded=set();members=0;nonpositive=set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():raise ValueError('ZIP_CRC_FAIL')
        for name in archive.namelist():
            if not name.endswith('.json'):continue
            raw=archive.read(name);obj=json.loads(raw)
            if not isinstance(obj,dict) or 'rows' not in obj:continue
            members+=1;rows,_,_=parse_member('FinMind',name,raw,period)
            for row in rows:
                if row['native_field']!='close':continue
                key=(row['stock_id'],row['date'])
                if row['status']=='QUARANTINE_OHLC':excluded.add(key);continue
                if decimal.Decimal(row['numeric_decimal_text'])<=0:nonpositive.add(key);continue
                if row['date_content_verified']:
                    points.append({'stock_id':row['stock_id'],'date':row['date'],'close':row['numeric_decimal_text']})
    if not points:raise ValueError('NO_REAL_PRICE_POINTS')
    features,conflicts=warmup_rows(points,target=period)
    if conflicts:raise ValueError('CONFLICTING_PRICE_INPUTS')
    by_key={(r['stock_id'],r['date']):r for r in features}
    checks=collections.Counter()
    with sqlite3.connect(':memory:') as db:
        db.execute('create table prices(symbol text,date text,close real,primary key(symbol,date))')
        db.executemany('insert into prices values(?,?,?)',[(p['stock_id'],p['date'],float(p['close'])) for p in points])
        for n in (5,10,20,60,120,240):
            sql=f'''select symbol,date,count(*) over w,avg(close) over w,
                100.0*(close/lag(close,{n}) over (partition by symbol order by date)-1.0)
                from prices window w as (partition by symbol order by date
                rows between {n-1} preceding and current row)'''
            for symbol,date,count,ma,ret in db.execute(sql):
                actual=by_key[(symbol,date)]
                for key,expected in [('ma_'+str(n),ma if count==n else None),('return_'+str(n),ret)]:
                    value=actual[key]
                    if expected is None:
                        if value is not None:raise ValueError('INSUFFICIENT_WINDOW_NOT_NULL')
                        checks['correct_nulls']+=1
                    else:
                        if value is None or abs(float(value)-expected)>1e-8*max(1,abs(expected)):raise ValueError('SQL_FORMULA_MISMATCH')
                        checks['numeric_comparisons']+=1
                    checks['all_comparisons']+=1
    if any(k in by_key for k in excluded|nonpositive):raise ValueError('INVALID_PRICE_ENTERED_FEATURES')
    y,m=map(int,period.split('-'));future_period=f'{y+(m==12)}-{m%12+1:02d}'
    future=points+[{'stock_id':points[0]['stock_id'],'date':future_period+'-01','close':'99999999'}]
    future_rows,_=warmup_rows(future,target=period)
    if {(r['stock_id'],r['date']):r for r in future_rows}!=by_key:raise ValueError('FUTURE_OBSERVATION_CHANGED_PAST')
    return {'status':'SAMPLE_FORMULA_ACCEPTANCE_PASS','approved':False,'period':period,'source':'FinMind',
            'parser_revision':PARSER_REVISION,'raw_archive_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'members_checked':members,'valid_price_points':len(points),'instruments':len({p['stock_id'] for p in points}),
            'excluded_ohlc_stock_dates':len(excluded),'excluded_nonpositive_close_stock_dates':len(nonpositive),
            'checks':dict(checks),'future_observation_independence':True,
            'limitations':['BOUNDED_SAMPLE','VALID_OBSERVATION_WINDOWS','UNADJUSTED_PRICES','NO_INDEPENDENT_SOURCE_GOLDEN','NO_UNIT_UNIVERSE_CALENDAR_PIT_APPROVAL']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True);parser.add_argument('--period',required=True)
    args=parser.parse_args();print(json.dumps(verify(args.archive,args.period),ensure_ascii=False,indent=2))
