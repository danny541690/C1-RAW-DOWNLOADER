"""Preserve rejected native bytes outside formal RAW; never certify their data."""
import gzip,hashlib
ROOT='1U5VHn3iPxnGbm2baUf27qYqt0Cq8wvBA'
def preserve(drive,source,raw,qa=False):
 if not isinstance(raw,bytes):raise ValueError('REJECTED_BYTES_REQUIRED')
 digest=hashlib.sha256(raw).hexdigest();stored=gzip.compress(raw,mtime=0);stored_sha=hashlib.sha256(stored).hexdigest()
 parent=drive.folder(ROOT,('QA_REJECTED_' if qa else 'REJECTED_')+source)
 name=digest+'.raw.gz';drive.direct_readback=True;drive.put(parent,name,stored,'application/gzip',overwrite=False)
 found=drive.find(parent,name)
 if not found:raise ValueError('REJECTION_EVIDENCE_NOT_FOUND')
 readback=drive.call(lambda:drive.api.files().get_media(fileId=found['id']))
 if hashlib.sha256(readback).hexdigest()!=stored_sha or hashlib.sha256(gzip.decompress(readback)).hexdigest()!=digest:raise ValueError('REJECTION_EVIDENCE_SHA')
 return dict(reference=found['id'],raw_sha256=digest,stored_sha256=stored_sha,encoding='gzip',raw_bytes=len(raw),readback_verified=True,accepted_as_raw=False)
