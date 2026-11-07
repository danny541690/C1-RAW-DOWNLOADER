#!/usr/bin/env python3
"""v0.95 R13: deterministic CAS/fencing and PIT preflight fault-injection model.

This tests a single-committer STATE CONTRACT, not GitHub/Drive actual atomic writes.
No network access; no durable CAS or official market-data publication.
"""
import dataclasses,datetime as dt,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"r13_single_pass"
@dataclasses.dataclass(frozen=True)
class Revision:
 generation:int=0
 owner:str=""
 fencing_epoch:int=0
 committed_sha:str=""
 upstream_sha:str=""
 def as_dict(self):return dataclasses.asdict(self)
class FencingError(Exception):pass
class InvalidEvidence(Exception):pass
def claim(record,expected_generation,runner,epoch):
 if record.generation!=expected_generation:raise FencingError("CAS_GENERATION_MISMATCH")
 if epoch<=record.fencing_epoch:raise FencingError("STALE_FENCING_EPOCH")
 if record.committed_sha:raise FencingError("IMMUTABLE_ALREADY_COMMITTED")
 if not runner:raise FencingError("MISSING_RUNNER_ID")
 return Revision(record.generation+1,runner,epoch,"",record.upstream_sha)
def commit(record,expected_generation,runner,epoch,content,expected_source_sha,readback_sha):
 if record.generation!=expected_generation:raise FencingError("CAS_GENERATION_MISMATCH")
 if record.owner!=runner or record.fencing_epoch!=epoch:raise FencingError("STALE_WRITER")
 if record.committed_sha:raise FencingError("IMMUTABLE_ALREADY_COMMITTED")
 digest=hashlib.sha256(content).hexdigest()
 if not expected_source_sha or not readback_sha or digest!=expected_source_sha or digest!=readback_sha:
  raise InvalidEvidence("SOURCE_SHA_OR_REMOTE_READBACK_MISMATCH")
 return Revision(record.generation+1,"",epoch,digest,digest)
def asof_allowed(first_published_at,asof,revision_at=None):
 """Unknown release dates cannot be used for historical research."""
 if not first_published_at or not asof:return False
 try:
  published=dt.datetime.fromisoformat(first_published_at.replace("Z","+00:00"))
  decision=dt.datetime.fromisoformat(asof.replace("Z","+00:00"))
  if published.tzinfo is None or decision.tzinfo is None:return False
  if revision_at:
   revised=dt.datetime.fromisoformat(revision_at.replace("Z","+00:00"))
   if revised.tzinfo is None or revised>decision:return False
  return published<=decision
 except (ValueError,TypeError):return False
def simulate():
 init=Revision()
 a=claim(init,0,"runner-A",1)
 failures=[]
 for name,fn in [
   ("STALE_RACE",lambda:claim(a,0,"runner-B",2)),
   ("WRONG_OWNER",lambda:commit(a,1,"runner-B",1,b"native","x","x")),
   ("MISSING_READBACK",lambda:commit(a,1,"runner-A",1,b"native",hashlib.sha256(b"native").hexdigest(),"")),
 ]:
  try:fn();failures.append("UNEXPECTED_PASS:"+name)
  except (FencingError,InvalidEvidence):pass
 sha=hashlib.sha256(b"native").hexdigest()
 committed=commit(a,1,"runner-A",1,b"native",sha,sha)
 try:claim(committed,committed.generation,"runner-B",2);failures.append("DUPLICATE_COMMIT_ALLOWED")
 except FencingError:pass
 assert not asof_allowed("2026-11-08T01:00:00Z","2026-11-07T00:00:00Z")
 assert not asof_allowed(None,"2026-11-07T00:00:00Z")
 assert not asof_allowed("2026-11-01T00:00:00Z","2026-11-07T00:00:00Z",
                            "2026-11-08T00:00:00Z")
 assert asof_allowed("2026-11-01T00:00:00Z","2026-11-07T00:00:00Z")
 return {"schema":"JARVIS_V095_R13_IN_MEMORY_FENCING_PRECHECK_V1",
   "status":"PASS_IN_MEMORY_MODEL_ONLY" if not failures else "FAIL_MODEL",
   "violations":failures,"cases":["race_generation","wrong_owner","missing_readback_sha",
      "immutable_once","unpublished_future","unknown_release","later_revision","valid_asof"],
   "actual_github_cas_verified":False,"actual_drive_commit_verified":False,
   "market_data_downloaded":0,"production_download_ready":False,
   "next_actual_proof":"One scoped officially published missing data item, two separate runners and Drive readback"}
def main():
 r=simulate();OUT.mkdir(exist_ok=True)
 (OUT/"result.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(r,ensure_ascii=False))
 return 0 if r["status"].startswith("PASS") else 2
if __name__=="__main__":sys.exit(main())
