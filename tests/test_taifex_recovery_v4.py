import copy
import datetime as dt
import unittest
from unittest.mock import patch
from scripts import v093_taifex_independent as m

class RecoveryTests(unittest.TestCase):
    def job(self,action='largeTraderFutDown',start='2009-02-01',end='2009-02-28'):
        return m.make_job('HISTORY|'+action+'|'+start[:7],m.SITE+'/cht/3/'+action,'csv',dt.date.fromisoformat(start),dt.date.fromisoformat(end),{'queryStartDate':start.replace('-','/'),'queryEndDate':end.replace('-','/'),'menuid1':''})
    def worker(self):
        w=object.__new__(m.Worker);w.state={'receipts':{}};w.direction='ASC';w.peer_recovered=0;w.evidence_recovered=0
        w.live=lambda:True;w.save=lambda:None;w.ctrl='control';w.saved=0
        w.request=lambda *args:(_ for _ in ()).throw(AssertionError('source must not be called'))
        return w
    def setup_peer(self):
        w=self.worker();job=self.job();peer=m.alias_job(job)
        raw='交易日期,契約,收盤價\n2009/02/02,TX,4200\n'.encode()
        old=dict(status='UNRESOLVED',error='HTTPError:HTTP Error 520',attempts=3,request=job)
        donor=dict(status='SAVED_BASIC_VERIFIED',request=peer,file_id='preserved',sha256=m.digest(raw),remote_readback_hash_verified=True)
        w.state['receipts']={job['key']:old,peer['key']:donor};w.read_receipt_raw=lambda e:raw
        return w,job,peer,raw
    def test_peer_recovers_exhausted_without_source_or_rewrite(self):
        w,j,p,raw=self.setup_peer();donor=copy.deepcopy(w.state['receipts'][p['key']]);w.recover_existing()
        e=w.state['receipts'][j['key']];self.assertEqual(e['status'],'SAVED_BASIC_VERIFIED');self.assertEqual(e['file_id'],'preserved')
        self.assertEqual(e['source_request'],p);self.assertFalse(e['pit_verified']);self.assertEqual(w.peer_recovered,1)
        self.assertEqual(w.state['receipts'][p['key']],donor);w.recover_existing();self.assertEqual(w.peer_recovered,1)
    def test_peer_hash_mismatch_holds_and_cannot_redownload(self):
        w,j,p,raw=self.setup_peer();w.read_receipt_raw=lambda e:b'corrupt';w.recover_existing()
        e=w.state['receipts'][j['key']];self.assertTrue(e['integrity_hold']);self.assertEqual(e['status'],'UNRESOLVED');self.assertFalse(w.eligible(j))
    def test_peer_wrong_dates_or_filters_never_used(self):
        for change in [{'start':'2009-01-01'},{'fields':{'commodityId':'TX'}}]:
            w,j,p,raw=self.setup_peer();w.state['receipts'][p['key']]['request'].update(change)
            w.read_receipt_raw=lambda e:(_ for _ in ()).throw(AssertionError('unsafe peer'))
            w.recover_existing();self.assertEqual(w.peer_recovered,0)
    def test_alias_restricted_to_verified_official_routes(self):
        self.assertIsNone(m.alias_job(dict(self.job(),url='https://evil.test/largeTraderFutDown')))
        self.assertIsNone(m.alias_job(self.job('unknownDown')))
        self.assertIsNotNone(m.alias_job(self.job()))
    def test_retries_cooldown_cycles_and_migration_do_not_reset_cap(self):
        e=dict(status='UNRESOLVED',error='HTTPError:HTTP Error 520',attempts=3,retry_after_epoch=100)
        s=dict(receipts={'x':e},repair_revision='TAIFEX_NATIVE_FORMAT_REPAIR_V3_1_20261024')
        m.migrate_repairs(s);self.assertEqual(e['attempts'],3)
        m.prepare_transport_retries(s,99);self.assertEqual(e['attempts'],3)
        m.prepare_transport_retries(s,100);self.assertEqual(e['attempts'],0);self.assertEqual(e['transport_retry_cycle'],2)
        e['attempts']=3;m.prepare_transport_retries(s,100);self.assertEqual(e['transport_retry_cycle'],3)
        e['attempts']=3;m.prepare_transport_retries(s,100);m.migrate_repairs(s);self.assertEqual(e['attempts'],3)
        self.assertEqual(e['lifetime_attempts'],6)
    def test_unknown_failures_and_success_never_reopened(self):
        rows={k:dict(status=st,error=err,attempts=3) for k,st,err in [('parser','UNRESOLVED','ValueError:bad schema'),('html','UNRESOLVED','ValueError:API_ROUTE_RETURNS_SWAGGER_HTML'),('ok','SAVED_BASIC_VERIFIED','HTTPError:HTTP Error 520')]}
        before=copy.deepcopy(rows);s=dict(receipts=rows);m.prepare_transport_retries(s,1e20);self.assertEqual(rows,before)
    def test_legacy_swagger_reclassified_from_sha_matching_evidence(self):
        w=self.worker();w.direction='DESC';raw=b'<html><title>Swagger UI</title></html>'
        job=m.make_job('API|2026-10-24|/bad','https://openapi.taifex.com.tw/v1/bad','snapshot',dt.date(2026,10,24),dt.date(2026,10,24))
        e=dict(status='UNRESOLVED',attempts=3,request=job,error='JSONDecodeError:Expecting value',response_sha256=m.digest(raw))
        w.state['receipts'][job['key']]=e;w.d=type('D',(),{'read':lambda *a:raw})()
        w.recover_existing();e=w.state['receipts'][job['key']];self.assertIn('SWAGGER_HTML',e['error']);self.assertEqual(e['attempts'],3)
    def test_asc_does_not_repair_imported_desc_partition(self):
        w,j,p,raw=self.setup_peer();w.direction='DESC';w.recover_existing();self.assertEqual(w.peer_recovered,0)
    def test_transport_recovery_uses_official_alias_and_records_actual_request(self):
        w=self.worker();j=self.job();w.state['receipts'][j['key']]=dict(status='UNRESOLVED',attempts=0,lifetime_attempts=3,error='HTTPError:HTTP Error 520')
        called=[];raw='交易日期,契約\n2009/02/02,TX\n'.encode();w.request=lambda url,fields:called.append(url) or raw
        w.persist_raw=lambda job,raw,entry,ev:entry.update(status='SAVED_BASIC_VERIFIED')
        w.process(j);self.assertEqual(called,[m.SITE+'/cht/3/dlLargeTraderFutDown']);self.assertEqual(w.state['receipts'][j['key']]['lifetime_attempts'],4)

    def test_interrupted_request_retains_attempts_and_is_bounded_retryable(self):
        e=dict(status='REQUEST_INTENT',attempts=3,lifetime_attempts=3,request=self.job())
        s=dict(receipts={'x':e});m.reconcile_interrupted_intents(s)
        self.assertEqual(e['attempts'],3);self.assertTrue(e['interrupted_request'])
        m.prepare_transport_retries(s,1e20);self.assertEqual(e['transport_retry_cycle'],2);self.assertEqual(e['lifetime_attempts'],3)
    def test_interrupted_reconciliation_does_not_touch_saved_or_parser(self):
        rows={'ok':dict(status='SAVED_BASIC_VERIFIED',sha256='keep'),'bad':dict(status='UNRESOLVED',error='ValueError:layout')}
        before=copy.deepcopy(rows);m.reconcile_interrupted_intents(dict(receipts=rows));self.assertEqual(rows,before)
