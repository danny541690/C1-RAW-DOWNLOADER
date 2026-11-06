import collections,hashlib,io,json,os,re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());s=build("drive","v3",credentials=c,cache_discovery=False)
 original=s.files().get_media(fileId="1mj0-Jr46atOhDoGRTxS-G17aShKF64PS").execute()
 rows=[];seen=set()
 for line in original.decode("utf-8-sig").splitlines():
  if not line.startswith("| "):continue
  cols=[z.strip() for z in line.strip().strip("|").split("|")]
  if len(cols)!=7 or not re.fullmatch(r"[A-Z][A-Z0-9_]*",cols[0]) or cols[0]=="ID":continue
  key,name,group,unit,source,evidence,gap=cols
  if key in seen:raise ValueError("DUPLICATE_INDICATOR")
  seen.add(key)
  rows.append(dict(id=key,name=name,group=group,unit=unit,legacy_source=source,legacy_evidence=evidence,legacy_gap=gap,source_contract="CANDIDATE",formula="DEFINITION_PENDING",value=None,pit_verified=False,queryable=False,missing_reason="NOT_COMPUTED"))
 if len(rows)!=443:raise ValueError("EXPECTED_443_ACTUAL_"+str(len(rows)))
 report=dict(schema="JARVIS_V095_443_CANDIDATE_CATALOG",source_v093_sha256=hashlib.sha256(original).hexdigest(),count=len(rows),groups=dict(collections.Counter(v["group"] for v in rows)),release_approved=False,pit_verified=False,indicators=rows)
 blob=(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode()
 name="JARVIS_V095_443_CATALOG_RUN_"+os.environ.get("GITHUB_RUN_ID","local")+".json"
 f=s.files().create(body=dict(name=name,parents=["1igeNb_PpOgiYV13_TB1rfEPNsAoisc_Z"]),media_body=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/json",resumable=False),fields="id").execute()
 assert hashlib.sha256(s.files().get_media(fileId=f["id"]).execute()).digest()==hashlib.sha256(blob).digest()
 print(json.dumps(dict(indicators=len(rows),drive_file_id=f["id"],verified_catalog_sha=True,computed=0,pit_verified=False),ensure_ascii=False))
if __name__=="__main__":main()
