import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
from scripts import v093_taifex_independent as m

class CatalogTests(unittest.TestCase):
    def form(self,action='productOrderDown'):
        return dict(action=action,source_page=m.SITE+'/cht/3/productOrderView',fields=dict(queryStartDate='',queryEndDate=''),first='2000-01-01',last='2026-10-22')
    def test_import_new_form_preserves_receipts_and_existing_bounds(self):
        state=dict(catalog={'keep':dict(first='2010-01-01')},receipts={'saved':dict(status='SAVED_BASIC_VERIFIED',sha256='keep')})
        old=copy.deepcopy(state);peer=dict(run_id='123',catalog={'productOrderDown':self.form(),'keep':{}})
        self.assertEqual(m.import_history_catalog(state,peer),['productOrderDown']);self.assertEqual(state['receipts'],old['receipts']);self.assertEqual(state['catalog']['keep'],old['catalog']['keep'])
        self.assertEqual(m.import_history_catalog(state,peer),[])
    def test_reject_unsafe_form_origins_filters_and_dates(self):
        for fields in [dict(source_page='https://evil.test/page'),dict(fields={'queryStartDate':[],'queryEndDate':''}),dict(first='2026-10-22',last='2000-01-01'),dict(action='differentDown')]:
            f=self.form();f.update(fields);s=dict(catalog={});self.assertEqual(m.import_history_catalog(s,dict(catalog={'productOrderDown':f})),[])
    def job(self,action='productOrderDown',fields=None):
        return m.make_job('HISTORY|'+action+'|2000-01',m.SITE+'/cht/3/'+action,'csv',dt.date(2000,1,1),dt.date(2000,1,31),fields or {'queryStartDate':'2000/01/01','queryEndDate':'2000/01/31'})
    def test_canonical_plan_retains_saved_alias_and_never_overwrites(self):
        a=self.job();b=m.alias_job(a);saved={b['key']:dict(status='SAVED_BASIC_VERIFIED',sha256='keep')};before=copy.deepcopy(saved)
        self.assertEqual(m.canonical_history_jobs([a,b],saved),[b]);self.assertEqual(saved,before)
    def test_different_dates_or_product_scope_not_deduplicated(self):
        a=self.job();b=m.alias_job(a);b['fields']=dict(a['fields'],commodityId='TX')
        self.assertEqual(len(m.canonical_history_jobs([a,b],{})),2)
        b=m.alias_job(a);b['end']='2000-01-30';self.assertEqual(len(m.canonical_history_jobs([a,b],{})),2)
    def test_new_catalog_expands_asc_without_crossing_partition(self):
        w=object.__new__(m.Worker);w.direction='ASC';w.today=dt.date(2026,10,25)
        w.state=dict(catalog={},receipts={},latest_trading_date='2026-10-22',futures_annual_years=[],options_annual_years=[])
        self.assertEqual(w.history_jobs(),[]);m.import_history_catalog(w.state,dict(catalog={'productOrderDown':self.form()}))
        jobs=w.history_jobs();self.assertEqual(jobs[0]['start'],'2000-01-01');self.assertEqual(jobs[-1]['end'],'2012-12-31');self.assertEqual(len(jobs),156)
    def worker(self):
        w=object.__new__(m.Worker);w.today=dt.date(2026,10,25);w.state={};w.live=lambda:True;w.save=lambda:None
        return w
    def test_tick_failure_not_mistaken_for_day_complete_and_retries_bounded(self):
        w=self.worker();w.page=lambda name:(_ for _ in ()).throw(TimeoutError('source timeout'))
        with patch.object(m,'TICK_PAGES',['x']),patch.object(m.time,'time',return_value=100):w.refresh_tick_catalog()
        self.assertNotIn('x',w.state['tick_page_attempted_dates']);self.assertEqual(w.state['tick_page_retry']['x']['attempts'],1)
        with patch.object(m,'TICK_PAGES',['x']),patch.object(m.time,'time',return_value=101):w.refresh_tick_catalog()
        self.assertEqual(w.state['tick_page_retry']['x']['attempts'],1)
        w.page=lambda name:b'<html></html>'
        with patch.object(m,'TICK_PAGES',['x']),patch.object(m.time,'time',return_value=1001):w.refresh_tick_catalog()
        self.assertEqual(w.state['tick_page_attempted_dates']['x'],'2026-10-25');self.assertNotIn('x',w.state['tick_page_retry'])
    def test_active_host_cooldown_does_not_consume_daily_tick_attempt(self):
        w=self.worker();w.state['source_backoff']={'www.taifex.com.tw':1000}
        w.page=lambda *a:(_ for _ in ()).throw(AssertionError('must not request'))
        with patch.object(m,'TICK_PAGES',['x']),patch.object(m.time,'time',return_value=100):w.refresh_tick_catalog()
        self.assertEqual(w.state['tick_page_attempted_dates'],{});self.assertEqual(w.state['tick_page_retry'],{})
    def test_cursor_results_remain_immediate_status_coalesces_and_final_forces(self):
        w=self.worker();w.direction='ASC';w.ctrl='control';w.started='start';w.saved=0;w.requests=0;w.history_jobs=lambda:[]
        w.state=dict(receipts={},catalog={},tick_jobs={});calls=[]
        w.d=type('D',(),{'put':lambda self,parent,name,*a,**k:calls.append(name)})()
        # Use real class method; the helper's save stub is for discovery tests only.
        with patch.object(m.time,'monotonic',return_value=100):m.Worker.save(w)
        with patch.object(m.time,'monotonic',return_value=101):m.Worker.save(w)
        self.assertEqual(calls.count('CURSOR.json'),2);self.assertEqual(calls.count('STATUS.json'),1)
        with patch.object(m.time,'monotonic',return_value=102):m.Worker.save(w,force_status=True)
        self.assertEqual(calls.count('STATUS.json'),2)

    def test_canonical_plan_preserves_empty_receipt_and_existing_retry_budget(self):
        a=self.job();b=m.alias_job(a)
        for old in [dict(status='SKIPPED_SOURCE_EMPTY',attempts=1),dict(status='UNRESOLVED',attempts=3)]:
            self.assertEqual(m.canonical_history_jobs([a,b],{a['key']:old}),[a])

    def test_migrate_reopens_only_failed_tick_page_markers(self):
        s=dict(tick_page_attempted_dates={'ok':'2026-10-25','failed':'2026-10-25'},tick_page_success_dates={'ok':'2026-10-25','failed':'2026-10-24'})
        m.migrate_repairs(s);self.assertEqual(s['tick_page_attempted_dates'],{'ok':'2026-10-25'})
        s['tick_page_attempted_dates']['failed']='new';m.migrate_repairs(s);self.assertEqual(s['tick_page_attempted_dates']['failed'],'new')
