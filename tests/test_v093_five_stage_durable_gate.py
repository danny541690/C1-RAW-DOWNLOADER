import hashlib
import unittest
from unittest.mock import patch
from scripts import v093_five_stage_durable_gate as gate

class DurableFiveStageGateTests(unittest.TestCase):
    def test_acquire_and_commit_with_fencing(self):
        state={'sha':'s1','payload':{'jobs':{}}}
        def read(url,token):
            return state['sha'],{'jobs':{k:dict(v) for k,v in state['payload']['jobs'].items()}}
        def put(url,token,sha,payload,message):
            if sha!=state['sha']:
                return False
            state['sha']='s'+str(int(state['sha'][1:])+1)
            state['payload']=payload
            return True
        with patch.object(gate,'_read',side_effect=read),patch.object(gate,'_put',side_effect=put):
            fence=gate.acquire('url','token','2026-10:RAW','owner1',now=100,ttl=10)
            self.assertEqual(fence,1)
            with self.assertRaises(gate.LeaseBusy):
                gate.acquire('url','token','2026-10:RAW','owner2',now=105,ttl=10)
            fence2=gate.acquire('url','token','2026-10:RAW','owner2',now=111,ttl=10)
            self.assertEqual(fence2,2)
            digest=hashlib.sha256(b'test').hexdigest()
            with self.assertRaises(gate.LeaseConflict):
                gate.commit('url','token','2026-10:RAW','owner1',fence,digest,now=112)
            self.assertTrue(gate.commit('url','token','2026-10:RAW','owner2',fence2,digest,now=112))
            row=state['payload']['jobs']['2026-10:RAW']
            self.assertFalse(row['certified'])
            self.assertEqual(row['status'],'DATA_PRESENT_PENDING_QA')
            self.assertEqual(row['sha256'],digest)
    def test_cas_conflict_retry(self):
        state={'sha':'s1','payload':{'jobs':{}},'first':True}
        def read(url,token):
            return state['sha'],{'jobs':{k:dict(v) for k,v in state['payload']['jobs'].items()}}
        def put(url,token,sha,payload,message):
            if state['first']:
                state['first']=False
                return False
            state['payload']=payload
            return True
        with patch.object(gate,'_read',side_effect=read),patch.object(gate,'_put',side_effect=put),patch.object(gate.time,'sleep'):
            self.assertEqual(gate.acquire('url','token','key','owner',now=100,ttl=5),1)
    def test_invalid_digest(self):
        with self.assertRaises(ValueError):
            gate._digest('wrong')
    def test_adapter_all_gates_required(self):
        raw={'sha256':'a'*64}
        qa={'raw_sha256':'a'*64}
        adapter={k:True for k in ('schema_ok','unit_ok','date_ok','pit_ok','numeric_ok','universe_ok')}
        adapter['approved_version']='v1'
        for stage in ('PRICE','FINANCIAL','CHIP'):
            self.assertEqual(gate.decide_adapter(stage,raw,qa,adapter),'ELIGIBLE_FOR_STAGING_NOT_CERTIFIED')
            for key in ('schema_ok','unit_ok','date_ok','pit_ok','numeric_ok','universe_ok'):
                broken=dict(adapter);broken[key]=False
                self.assertTrue(gate.decide_adapter(stage,raw,qa,broken).startswith('BLOCKED_'))
        self.assertEqual(gate.decide_adapter('PRICE',raw,{'raw_sha256':'b'*64},adapter),'BLOCKED_RAW_QA_DIGEST_MISMATCH')

if __name__=='__main__':
    unittest.main()
