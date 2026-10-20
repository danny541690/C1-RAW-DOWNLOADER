import datetime as dt,hashlib,json,unittest
from unittest.mock import patch
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_folder_registry import choose_folder
from scripts.v093_standard_r4 import parse_member,SCHEMA
from scripts.v093_layer02_governance import compare_candidates,GateBlocked,REQUIRED_QA,gate_release
from scripts.v093_release_publisher import validate_evidence,publish
from scripts.v093_daily_shadow import target_day
from scripts.v093_feature_shadow import compute_features
from scripts.v093_operations import repair_plan,aggregate_reports

class OperationalFixes(unittest.TestCase):
 def candidate(self,value):
  return dict(source='TWSE',stock_id='2330',period='2025-01-02',field='close',unit='TWD/share',definition_version='raw',as_of_mode='AS_KNOWN',value=value,**{k:True for k in ('schema_ok','unit_ok','date_ok','pit_ok','numeric_ok','universe_ok')})
 def test_nonfinite_candidates_rejected(self):
  for v in (float('nan'),float('inf'),float('-inf'),True):
   r=compare_candidates([self.candidate(v)],approved_sources=['TWSE']);self.assertEqual(r['status'],'BLOCKED');self.assertIsNone(r['chosen'])
 def test_invalid_tolerance_rejected(self):
  for t in (float('nan'),float('inf'),True,-1):
   with self.assertRaises(ValueError):compare_candidates([self.candidate(5)],approved_sources=['TWSE'],tolerance=t)
 def test_incomplete_identity_rejected(self):
  r=self.candidate(5);r.pop('unit');self.assertEqual(compare_candidates([r],approved_sources=['TWSE'])['status'],'BLOCKED')
 def test_financial_metric_and_context_retained(self):
  rows=[{'date':'2025-03-31','stock_id':'2330','type':'Revenue','origin_name':'營業收入','value':'9007199254740993','unit':'千元','report_type':'consolidated'},{'date':'2025-03-31','stock_id':'2330','type':'EPS','origin_name':'基本每股盈餘','value':'10.05','unit':'元/股'}]
  out,_,_=parse_member('FinMind','financial.json',json.dumps({'data':rows}).encode(),'2025-03')
  self.assertEqual([x['native_metric'] for x in out],['Revenue','EPS']);self.assertEqual(out[0]['numeric_decimal_text'],'9007199254740993')
  self.assertEqual(json.loads(out[0]['native_record_json']),rows[0]);self.assertEqual(out[0]['native_unit'],'千元');self.assertFalse(out[0]['unit_verified']);self.assertFalse(out[0]['pit_verified'])
  self.assertIn('native_metric',SCHEMA.names)
 def test_json_nonfinite_never_enters_candidate(self):
  with self.assertRaises(ValueError):parse_member('FinMind','financial.json',b'{"data":[{"date":"2025-03-31","stock_id":"2330","type":"EPS","value":NaN,"other":1}]}','2025-03')
 def test_only_nonempty_folder_selected(self):
  cs=[{'id':'empty'},{'id':'has-data'}]
  self.assertEqual(choose_folder(cs,{'empty':0,'has-data':1}),('has-data','ONLY_NONEMPTY_ALIAS'))
  self.assertEqual(len(cs),2)
 def test_ambiguous_nonempty_folders_blocked(self):
  with self.assertRaises(ValueError):choose_folder([{'id':'a'},{'id':'b'}],{'a':1,'b':1})
 def test_stale_folder_registry_blocked(self):
  with self.assertRaises(ValueError):choose_folder([{'id':'a'}],{},'deleted')
 def test_registry_flush_preserves_other_registered_paths(self):
  class D:
   raw=None
   def read(self,*a):return self.raw
   def put(self,p,n,b,*a,**k):self.raw=b
  d=D();a=FolderRegistry(d,'control');b=FolderRegistry(d,'control')
  def listing(_d,parent):return [{'id':parent+'-id','name':parent,'mimeType':'application/vnd.google-apps.folder'}]
  with patch('scripts.v093_folder_registry.ls',side_effect=listing):
   a.folder('a','a');b.folder('b','b')
  b.flush();a.flush();saved=json.loads(d.raw)
  self.assertEqual(set(saved['entries']),{'a/a','b/b'})
 def manifest(self):
  sha=hashlib.sha256(b'candidate').hexdigest()
  return {'kind':'APPROVED_STANDARD','qa':{k:True for k in REQUIRED_QA},'generation_id':'fixture-gen','parquet_sha256':sha,'input_digests':[sha],'scope':{'markets':['TWSE'],'fields':['close'],'from':'2025-01-02','to':'2025-01-02','expected_universe':1},'data_folder':'data','data_name':'candidate'}
 def evidence(self,m):
  bodies={};m['evidence']={}
  for k in REQUIRED_QA:
   body=json.dumps({'gate':k,'passed':True,'generation_id':m['generation_id'],'input_digests':m['input_digests'],'scope':m['scope'],'checker_commit':'fixture-commit'}).encode();name=k+'.json';bodies[name]=body;m['evidence'][k]={'name':name,'sha256':hashlib.sha256(body).hexdigest()}
  return bodies
 def test_flags_without_evidence_cannot_publish(self):
  with self.assertRaises(GateBlocked):validate_evidence(self.manifest(),lambda name:None)
 def test_corrupted_evidence_blocked(self):
  m=self.manifest();b=self.evidence(m);b['pit.json']=b'changed'
  with self.assertRaises(GateBlocked):validate_evidence(m,b.get)
 def test_wrong_generation_evidence_blocked(self):
  m=self.manifest();b=self.evidence(m);p=json.loads(b['pit.json']);p['generation_id']='other';b['pit.json']=json.dumps(p).encode();m['evidence']['pit']['sha256']=hashlib.sha256(b['pit.json']).hexdigest()
  with self.assertRaises(GateBlocked):validate_evidence(m,b.get)
 def test_unknown_universe_blocked(self):
  m=self.manifest();m['scope']['expected_universe']=0
  with self.assertRaises(GateBlocked):validate_evidence(m,lambda n:None)
 def test_bad_digest_release_blocked(self):
  m=self.manifest();m['input_digests']=['not-a-digest']
  with self.assertRaises(GateBlocked):gate_release(m)
 def test_pointer_conflict_has_no_writes(self):
  m=self.manifest();proofs=self.evidence(m)
  class D:
   writes=[]
   def read(self,parent,name):
    if name=='candidate':return b'candidate'
    if name=='ACTIVE_APPROVED_RELEASE.json':return b'{"generation_id":"newer"}'
    return proofs.get(name)
   def put(self,*a,**k):self.writes.append((a,k))
  d=D()
  with self.assertRaises(GateBlocked):publish(d,'control',m,'expected-old')
  self.assertFalse(d.writes)
 def test_warmup_off_by_one_and_golden(self):
  points=[('2025-01-'+str(i).zfill(2),str(i*10)) for i in range(1,5)]
  out=compute_features(points,(3,));self.assertIsNone(out[1]['ma_3']);self.assertEqual(out[2]['ma_3'],'20');self.assertIsNone(out[2]['return_3']);self.assertEqual(out[3]['return_3'],'300')
 def test_240_return_requires_241_points(self):
  first=dt.date(2025,1,1);points=[((first+dt.timedelta(days=i)).isoformat(),str(i+1)) for i in range(241)]
  out=compute_features(points,(240,));self.assertIsNone(out[239]['return_240']);self.assertEqual(out[240]['ma_240'],'121.5');self.assertEqual(out[240]['return_240'],'24000')
 def test_duplicate_or_invalid_prices_blocked(self):
  for p in ([('2025-01-01','1'),('2025-01-01','2')],[('2025-01-02','1'),('2025-01-01','2')],[('2025-01-01','0')],[('2025-01-01','NaN')]):
   with self.assertRaises(ValueError):compute_features(p)
 def test_target_before_close_and_weekend(self):
  tz=dt.timezone(dt.timedelta(hours=8));self.assertEqual(target_day(dt.datetime(2026,10,20,9,tzinfo=tz)).isoformat(),'2026-10-19');self.assertEqual(target_day(dt.datetime(2026,10,19,9,tzinfo=tz)).isoformat(),'2026-10-16')
 def test_repair_only_targeted_sources(self):
  p=repair_plan();self.assertEqual(len(p),22);self.assertEqual(p[0]['key'],'2025-07');self.assertEqual(p[1]['sources'],['MOPS','FinMind']);self.assertEqual(len({x['key'] for x in p}),22)
 def test_processing_is_not_approval(self):
  r=aggregate_reports([('2025-01_NATIVE_R3_20261020_1_AUDIT.json',{'period':'2025-01','status':'STAGING_NOT_APPROVED','archives':[{'status':'STRUCTURAL_READBACK_PASS','cells':100,'unresolved_members':2}]})])
  self.assertFalse(r['2025-01']['R3']['approved']);self.assertEqual(r['2025-01']['R3']['unresolved_occurrences'],2)

if __name__=='__main__':unittest.main()
