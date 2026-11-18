import unittest
from copy import deepcopy
from hashlib import sha256
from scripts.v097_r3_formal_release_contracts import (
    certified_contract,validate_g3,validate_g4,certificate,
    handover_decision,full_reconcile,confirm_g5_readback,COUNTS,COHORT)
SHA=sha256(b"frozen-bronze").hexdigest()
PROOF_SHA=sha256(b"independent-proof").hexdigest()
ROW={"source":"TDCC","source_id":"TDCC-FROZEN-01","source_sha256":SHA,"data_date":"2017-06-30"}
G2={"source":"TDCC","source_id":ROW["source_id"],"content_sha256":SHA,
    "dataset":"SHAREHOLDING_DISTRIBUTION","template_id":"tdcc-2017-native","start_date":"2008-07-01",
    "end_date":"2026-12-31","official_reference":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
    "official_evidence_id":"immutable-approved-id","contract_version":"g2-period-1",
    "required_fields":["security_id","holders"],"approved_aliases":{"股票代號":"security_id"},
    "publication_asof_verified":True,"official_attested":True}
G3={"source_id":ROW["source_id"],"content_sha256":SHA,"dataset":G2["dataset"],
    "g2_contract_version":"g2-period-1","full_file_scanned":True,
    "native_units_verified":True,"types_and_keys_verified":True,"row_count":30,
    "validation_errors":0,"observed_fields":["security_id","holders"],
    "g2_required_fields":["security_id","holders"],
    "parser_version":"g3-1","independent_evidence_id":"immutable-g3"}
G4={"source_id":ROW["source_id"],"content_sha256":SHA,"dataset":G2["dataset"],
    "g2_contract_version":"g2-period-1","g3_parser_version":"g3-1",
    "mapping_version":"g4-1","target_fields":{"security_id":"stock_id","holders":"holder_count"},
    "g3_observed_fields":["security_id","holders"],
    "units_verified":True,"time_basis_verified":True,"security_identity_asof_verified":True,
    "numeric_semantics_verified":True,"independent_evidence_id":"immutable-g4","materialized":False}
GATES={"G1":"PASS","G2":"PASS","G3":"PASS","G4":"PASS"}
PROOFS={g:{"independent_evidence_id":"verified-"+g,"durably_committed":True,
           "evidence_sha256":PROOF_SHA} for g in ("G1","G2","G3","G4")}

class R3FormalReleaseTests(unittest.TestCase):
    def test_valid_contract_chain_staging_only(self):
        a=certified_contract(G2,ROW)
        self.assertEqual(a["status"],"PASS")
        b=validate_g3(G3,ROW,a)
        self.assertEqual(b["status"],"PASS")
        c=validate_g4(G4,ROW,a,b)
        self.assertEqual(c["status"],"PASS")
        g5=certificate(ROW,GATES,PROOFS,writer_fence="nonempty-real-token",durable_readback=True)
        self.assertEqual(g5["status"],"CANDIDATE")
        self.assertEqual(confirm_g5_readback(g5,g5["certificate"])["status"],"PASS")
        self.assertEqual(confirm_g5_readback(g5,{**g5["certificate"],"source_id":"tampered"})["status"],"HOLD")
        self.assertFalse(g5["certificate"]["silver_materialized"])
    def test_g2_rejects_guess_and_wrong_era(self):
        p=deepcopy(G2);p["official_attested"]=False
        self.assertEqual(certified_contract(p,ROW)["status"],"HOLD")
        p=deepcopy(G2);p["end_date"]="2010-12-31"
        self.assertEqual(certified_contract(p,ROW)["status"],"HOLD")
        p=deepcopy(G2);p["content_sha256"]="b"*64
        self.assertEqual(certified_contract(p,ROW)["status"],"HOLD")
    def test_g3_proof_cannot_inherit_candidate_without_scan(self):
        g2=certified_contract(G2,ROW)
        p=deepcopy(G3);p["full_file_scanned"]=False
        self.assertEqual(validate_g3(p,ROW,g2)["status"],"HOLD")
        p=deepcopy(G3);p["row_count"]=0
        self.assertEqual(validate_g3(p,ROW,g2)["status"],"HOLD")
        p=deepcopy(G3);p["g2_contract_version"]="old"
        self.assertEqual(validate_g3(p,ROW,g2)["status"],"HOLD")
    def test_g3_and_g4_reject_missing_source_semantics(self):
        g2=certified_contract(G2,ROW)
        g3_bad=deepcopy(G3);g3_bad["observed_fields"]=["security_id","not_found"]
        self.assertEqual(validate_g3(g3_bad,ROW,g2)["status"],"HOLD")
        g3=validate_g3(G3,ROW,g2)
        g4_bad=deepcopy(G4);g4_bad["target_fields"]["not_verified"]="unrelated_target"
        self.assertEqual(validate_g4(g4_bad,ROW,g2,g3)["status"],"HOLD")
    def test_g4_requires_real_units_pit_and_no_silver(self):
        g2=certified_contract(G2,ROW);g3=validate_g3(G3,ROW,g2)
        for key in ("units_verified","time_basis_verified","security_identity_asof_verified",
                    "numeric_semantics_verified"):
            bad=deepcopy(G4);bad[key]=False
            self.assertEqual(validate_g4(bad,ROW,g2,g3)["status"],"HOLD",key)
        bad=deepcopy(G4);bad["materialized"]=True
        self.assertEqual(validate_g4(bad,ROW,g2,g3)["status"],"HOLD")
    def test_g5_blocks_without_fencing_and_durable_receipts(self):
        self.assertEqual(certificate(ROW,GATES,PROOFS,writer_fence="",durable_readback=True)["status"],"HOLD")
        self.assertEqual(certificate(ROW,GATES,PROOFS,writer_fence="fence",durable_readback=False)["status"],"HOLD")
        bad=deepcopy(PROOFS);bad["G2"]["durably_committed"]=False
        self.assertEqual(certificate(ROW,GATES,bad,writer_fence="fence",durable_readback=True)["status"],"HOLD")
        bad=deepcopy(GATES);bad["G4"]="PENDING"
        self.assertEqual(certificate(ROW,bad,PROOFS,writer_fence="fence",durable_readback=True)["status"],"HOLD")
    def test_old_writers_block_handover(self):
        args={"old_runs_active":2,"cron_disabled":False,"redispatch_disabled":False,
              "old_master_snapshot":True,"old_checkpoint_snapshot":True,
              "exclusive_writer_fence":""}
        self.assertEqual(handover_decision(**args)["status"],"HOLD")
        self.assertEqual(handover_decision(**{**args,"old_runs_active":0,
             "cron_disabled":True,"redispatch_disabled":True,
             "exclusive_writer_fence":"valid-fence"})["status"],"PASS")
    def test_frozen_cohort_blocks_unsigned_ready(self):
        items=[]
        for source,n in COUNTS.items():
            items.extend({"source_id":f"{source}:{i}","source":source,"status":"HOLD"}
                         for i in range(n))
        self.assertEqual(len(items),COHORT)
        self.assertTrue(full_reconcile(items)["all_terminal"])
        with self.assertRaises(ValueError):full_reconcile(items,require_baseline=True)
        items[0]["status"]="SILVER_READY"
        with self.assertRaises(ValueError): full_reconcile(items)
        items[0]["g5_durable_readback"]=True
        att={"source_id":items[0]["source_id"],"source":items[0]["source"],"source_sha256":SHA,"status":"SILVER_READY"}
        from scripts.v097_r3_gate_core import digest
        items[0]["source_sha256"]=SHA
        items[0]["g5_certificate"]=att
        items[0]["g5_certificate_sha256"]=digest(att)
        self.assertEqual(full_reconcile(items)["silver_ready"],1)
        items[0]["source_id"]=items[1]["source_id"]
        with self.assertRaises(ValueError):full_reconcile(items)
if __name__=="__main__":unittest.main()
