#!/usr/bin/env python3
"""Real v0.95 governing table completion gate. No network, no mutation.

A CSV with only a header does NOT represent an operational manifest/queue.
CANDIDATE contracts must never be promoted to production source READY.
"""
import csv,json,pathlib,sys,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"r12_governance_gaps"
FILES={"manifest":"governance/v095/MANIFEST_INDEX.csv",
       "checkpoint":"governance/v095/CHECKPOINTS.csv",
       "registry":"governance/v095/SOURCE_REGISTRY.csv",
       "contracts":"governance/v095/DATASET_CONTRACTS.csv"}
def read_rows(root,filename):
 with (root/filename).open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))
def assess(root=ROOT):
 data={name:read_rows(root,p) for name,p in FILES.items()}
 flags=json.loads((root/"governance/v095/PHASE1_FLAGS.json").read_text())
 contract_counts=dict(collections.Counter(str(x.get("status","")).strip() for x in data["contracts"]))
 registry_counts=dict(collections.Counter(str(x.get("dataset_contract_status","")).strip() for x in data["registry"]))
 verified=sum(x.get("status") in ("READY_FOR_BRONZE_PRODUCTION","SIGNED_VERIFIED") for x in data["contracts"])
 has_checkpoint=any(x.get("commit_ack")=="COMMITTED" and x.get("last_committed_sha256") for x in data["checkpoint"])
 has_manifest=any(x.get("bronze_sha256") and x.get("readback_status")=="VERIFIED" for x in data["manifest"])
 report={"schema":"JARVIS_V095_R12_PRODUCTION_GOVERNANCE_GAP_V1",
  "manifest_data_rows":len(data["manifest"]),
  "checkpoint_data_rows":len(data["checkpoint"]),
  "source_registry_rows":len(data["registry"]),
  "dataset_contract_rows":len(data["contracts"]),
  "source_registry_contract_status_counts":registry_counts,
  "dataset_contract_status_counts":contract_counts,
  "production_ready_dataset_contracts":verified,
  "durable_committed_checkpoint_observed":has_checkpoint,
  "verified_bronze_manifest_observed":has_manifest,
  "bulk_approved":flags.get("BULK_COPY_APPROVED"),
  "research_release_approved":flags.get("RELEASE_APPROVED"),
  "production_backfill_ready":bool(verified and has_manifest and has_checkpoint and flags.get("BULK_COPY_APPROVED") is True),
  "source_download_tasks_released":0,
  "repair_queue_decision":"BLOCK_BULK_UNTIL_DATASET_CONTRACTS_AND_ATOMIC_MANIFEST_CHECKPOINTS_PROVED",
  "required_next_actions":[
    "Map R12 metadata index to real object Drive id and byte SHA; do not assume filename implies certified native source.",
    "Identify one official dataset/date actually absent and already published, sign contract and PIT-independent Bronze gate.",
    "Implement and prove v0.95 single-committer CAS/fencing with immutable Drive object and sha256 readback.",
    "Write genuine manifest and durable checkpoint evidence only after real T2 commit, not synthetic readiness rows.",
    "For eligible task only, enable bounded T2 one-unit test, then T3/T4; never automatically unlock 323 months."
  ]}
 return report
def main():
 r=assess()
 OUT.mkdir(exist_ok=True)
 (OUT/"result.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(r,ensure_ascii=False))
 if r["bulk_approved"] is not False or r["research_release_approved"] is not False:return 2
 return 0
if __name__=="__main__":sys.exit(main())
