"""Observe GitHub quota without leaking credentials; wait before acquiring locks."""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
import http.client


def rate_fields(headers):
    out={}
    for key in ('limit','remaining','reset','used'):
        try:out[key]=int(headers.get('X-RateLimit-'+key,headers.get('X-RateLimit-'+key.title(),headers.get('x-ratelimit-'+key,''))))
        except (ValueError,TypeError):out[key]=None
    out['retry_after']=headers.get('Retry-After')
    return out


def open_json(request,timeout=35):
    # Only read-only requests can be replayed after an ambiguous transport error.
    attempts=4 if request.get_method()=='GET' else 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request,timeout=timeout) as response:
                return json.load(response),rate_fields(response.headers)
        except urllib.error.HTTPError as exc:
            if exc.code in (403,429):
                info=rate_fields(exc.headers)
                try:message=str(json.loads(exc.read(4096)).get('message',''))[:200]
                except (ValueError,UnicodeDecodeError):message=str(exc.reason)[:100]
                print('GITHUB_API_BACKOFF '+json.dumps(dict(http_status=exc.code,message=message,**info)),flush=True)
            if exc.code not in (500,502,503,504) or attempt+1>=attempts:raise
        except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.IncompleteRead):
            if attempt+1>=attempts:raise
        print('GITHUB_READ_TRANSIENT_RETRY '+str(attempt+1),flush=True)
        time.sleep(min(2**attempt,8))


def wait_for_budget(minimum=400,max_wait=1200):
    token=os.environ['GH_TOKEN'];deadline=time.monotonic()+max_wait
    while True:
        request=urllib.request.Request('https://api.github.com/rate_limit',headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        result,headers=open_json(request)
        core=result['resources']['core']
        info=dict(limit=core['limit'],remaining=core['remaining'],reset=core['reset'])
        print('GITHUB_BUDGET_PROBE '+json.dumps(info,sort_keys=True),flush=True)
        if info['remaining']>=minimum:return info
        delay=max(5,info['reset']-time.time()+3)
        if time.monotonic()+delay>deadline:raise RuntimeError('GITHUB_BUDGET_WAIT_LIMIT_REACHED_NO_LOCK_ACQUIRED')
        # Runner waits happen before any lease or request intent is acquired.
        while delay>0:
            step=min(30,delay);time.sleep(step);delay-=step


def main():
    p=argparse.ArgumentParser();p.add_argument('--minimum',type=int,default=400);p.add_argument('--max-wait',type=int,default=1200)
    a=p.parse_args();wait_for_budget(a.minimum,a.max_wait)


if __name__=='__main__':main()

