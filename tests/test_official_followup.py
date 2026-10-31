import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v093_official_followup import calendar,classify,eligible,discover,repair_row,EmptyQueryAdapter,metadata
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor,ApplicabilityUnproven
from test_source_coordination import SQLiteCAS
from test_native_repair import FakeDrive
from test_problem_recovery import retained,sha

class OfficialFollowupTests(unittest.TestCase):
 def payload(self,year=2026):
  return dict(stat='ok',queryYear=year,date=str(year)+'0101',title=str(year-1911)+' 年市場開休市日期',data=[[str(year)+'-01-01','開國紀念日','依規定放假1日。'],[str(year)+'-01-02','國曆新年開始交易日','春節放假依另公告'],[str(year)+'-02-12','市場無交易，僅辦理結算交割',''],[str(year)+'-03-03','其他說明','請見公告']])
 def test_calendar_preserves_open_dates_and_unknowns(self):
  proof=calendar(json.dumps(self.payload()).encode(),2026,'https://www.twse.com.tw/example')
  self.assertEqual(proof['closed'],['2026-01-01','2026-02-12']);self.assertEqual(proof['opened'],['2026-01-02']);self.assertEqual(proof['unclassified'],['2026-03-03'])
 def test_wrong_year_and_conflicting_scope_are_rejected(self):
  for field,value in [('queryYear',2025),('date','20250101'),('title','114 年市場開休市日期')]:
   obj=self.payload();obj[field]=value
   with self.assertRaisesRegex(ValueError,'YEAR'):calendar(json.dumps(obj).encode(),2026,'url')
 def test_roc_year_is_normalized_without_guessing_current_year(self):
  obj=self.payload();obj['queryYear']=115
  self.assertEqual(calendar(json.dumps(obj).encode(),2026,'url')['year'],2026)
  obj.pop('queryYear');obj.pop('date');obj.pop('title')
  with self.assertRaisesRegex(ValueError,'UNPROVEN'):calendar(json.dumps(obj).encode(),2026,'url')
 def test_weekday_absence_is_not_certified_as_trading_or_exception(self):
  prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',definition=dict(source='TWSE',period='2026-03-04'))
  proof=calendar(json.dumps(self.payload()).encode(),2026,'url')
  self.assertIsNone(classify(prior,{'2026':proof},dict(national_weekend_evidence='official')))
 def test_saturday_rule_does_not_remove_2000_trading_days(self):
  prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',definition=dict(source='TPEx',period='2000-01-08'))
  config=dict(national_weekend_evidence='official');self.assertIsNone(classify(prior,{},config))
  prior['definition']['period']='2001-01-06';self.assertIsNotNone(classify(prior,{},config))
 def test_discovery_keeps_only_observed_official_links(self):
  text='<script src="/assets/pricing.js"></script><script src="https://evil.invalid/private.js"></script><form action="/Hist/download"></form><div data-api="/www/zh-tw/afterTrading/dailyQuotesHist"></div>'
  result=discover(text,'https://www.tpex.org.tw/history')
  self.assertEqual(result['scripts'],['https://www.tpex.org.tw/assets/pricing.js']);self.assertFalse(result['route_verified_for_download'])
  self.assertIn('https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotesHist',result['observed_routes'])
 def test_no_calendar_or_unproved_legacy_route_cannot_download(self):
  task=retained(b'bad',source='TPEx',period='2006-08-01',category='prices');prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',attempts=1,raw_sha256=sha(b'bad'))
  self.assertFalse(eligible(task,prior,{}));self.assertFalse(eligible(task,prior,{'2006':{}}))
  task['definition']['period']='2026-08-03';task['execution_contract']['period']='2026-08-03';self.assertTrue(eligible(task,prior,{'2026':{}}))
  prior['attempts']=4;self.assertFalse(eligible(task,prior,{'2026':{}}))
 def test_empty_requery_uses_final_request_and_preserves_original(self):
  raw=json.dumps(dict(stat='很抱歉，沒有符合條件的資料!'),ensure_ascii=False).encode();task=retained(raw,source='TWSE',period='2026-09-29',category='prices_indices');task['attempts']=3
  prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',attempts=3,raw_sha256=sha(raw));row=repair_row(task,prior,dict(raw_sha256='a'*64))
  good=json.dumps(dict(stat='OK',date='20260929',tables=[dict(fields=['代號'],data=[[str(i)] for i in range(1001,1301)])])).encode()
  with tempfile.TemporaryDirectory() as tmp:
   c=Coordinator(SQLiteCAS(Path(tmp)/'db'),'TWSE',ttl=600);c.update(lambda s:s['tasks'].update({row['definition']['key']:row}));drive=FakeDrive();drive.data['original-file']=raw
   a=EmptyQueryAdapter(c,drive,dict(source='TWSE',key=row['definition']['key']),row)
   with patch.object(a,'http',return_value=good) as http:result=Executor(c,a).one('DESC','followup')
   self.assertEqual(http.call_count,1);self.assertEqual(c.store.read('TWSE')[1]['tasks'][row['definition']['key']]['attempts'],4)
   self.assertEqual(drive.data['original-file'],raw);self.assertNotEqual(result['reference'],'original-file');self.assertFalse(result['full_acceptance'])
 def test_metadata_attempts_survive_cleanup_and_never_issue_fifth_get(self):
  with tempfile.TemporaryDirectory() as tmp:
   cas=SQLiteCAS(Path(tmp)/'db');state=dict(source='TWSE',tasks={})
   with patch('scripts.v093_official_followup.GitCAS',return_value=cas),patch('scripts.v093_official_followup.reserve'),patch('scripts.v093_official_followup.request',return_value=b'{}') as get:
    for i in range(5):metadata(Path(tmp),'TWSE','2026|calendar','https://www.twse.com.tw/calendar?v='+str(i),state,None,lambda:None)
   self.assertEqual(get.call_count,4);self.assertEqual(state['metadata_attempts']['2026|calendar'],4)

if __name__=='__main__':unittest.main()
