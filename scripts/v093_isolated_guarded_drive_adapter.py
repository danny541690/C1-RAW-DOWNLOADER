"""Isolated five-stage Drive adapter: lease -> immutable content name -> readback -> pending QA.

This is not a cross-system atomic transaction. A crash after put leaves an orphan
that a later owner must verify and reconcile. No automatic certification.
"""
import hashlib
import time
from scripts.v093_five_stage_durable_gate import acquire,commit,LeaseConflict

def immutable_name(key,payload):
    if not isinstance(payload,bytes) or not payload:
        raise ValueError('EMPTY_OR_INVALID_RAW')
    if '/' in key or '\\' in key or not key:
        raise ValueError('UNSAFE_KEY')
    return key+'_'+hashlib.sha256(payload).hexdigest()+'.bin'

def guarded_put(drive,parent,key,payload,manifest_url,token,owner,now=None,ttl=600):
    if not isinstance(payload,bytes) or not payload:
        raise ValueError('EMPTY_OR_INVALID_RAW')
    now=int(time.time() if now is None else now)
    digest=hashlib.sha256(payload).hexdigest()
    filename=immutable_name(key,payload)
    fence=acquire(manifest_url,token,key,owner,now=now,ttl=ttl)
    # Existing immutable names are only accepted if their bytes match.
    # Drive.put already does SHA readback and refuses different existing bytes.
    drive.put(parent,filename,payload,'application/octet-stream',overwrite=False)
    saved=drive.read(parent,filename)
    if saved is None or hashlib.sha256(saved).hexdigest()!=digest:
        raise ValueError('DRIVE_READBACK_SHA_MISMATCH')
    # Never mark as certified. An expired lease or takeover rejects this commit.
    commit(manifest_url,token,key,owner,fence,digest,now=int(time.time() if now is None else now))
    return {'name':filename,'sha256':digest,'status':'DATA_PRESENT_PENDING_QA','certified':False,'fence':fence}
