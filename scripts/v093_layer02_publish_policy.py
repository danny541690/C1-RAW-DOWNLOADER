"""Publish approved design *policy document only* to C1 v0.93 00_System/Policies.
No RAW, STANDARD Parquet, QA or release pointer changes.
"""
from pathlib import Path
import hashlib,json,datetime
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_standard_r1 import C1
def main():
 d=Drive(service())
 policy=d.folder(d.folder(C1,"00_System"),"Policies")
 content=Path("docs/v093_layer02_incremental_governance_r1.md").read_bytes()
 name="C1_0.93_STANDARD_MULTI_SOURCE_INCREMENTAL_GOVERNANCE_R1.md"
 d.put(policy,name,content,"text/markdown",overwrite=False)
 report={"status":"POLICY_SAVED_AND_READBACK_VERIFIED","name":name,"sha256":hashlib.sha256(content).hexdigest(),
 "folder":policy,"generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "limitation":"DESIGN_ONLY: NOT GOLDEN_COPY_DEPLOYMENT_OR_PIT_CERTIFICATION"}
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
