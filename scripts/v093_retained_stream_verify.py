"""Bounded streaming verification of retained Drive bytes, without market fetches."""
import hashlib
class HashSink:
 def __init__(self,limit=300_000_000):self.limit=limit;self.bytes=0;self.hash=hashlib.sha256()
 def write(self,data):
  if self.bytes+len(data)>self.limit:raise ValueError('RETAINED_SIZE_LIMIT')
  self.hash.update(data);self.bytes+=len(data);return len(data)
def verify(api,file_id,expected):
 from googleapiclient.http import MediaIoBaseDownload
 before=api.files().get(fileId=file_id,fields='size,version').execute()
 sink=HashSink()
 downloader=MediaIoBaseDownload(sink,api.files().get_media(fileId=file_id),chunksize=8*1024*1024)
 done=False
 while not done:_,done=downloader.next_chunk(num_retries=3)
 after=api.files().get(fileId=file_id,fields='size,version').execute()
 return dict(file_id=file_id,bytes=sink.bytes,expected_sha256=expected,actual_sha256=sink.hash.hexdigest(),
  unchanged_version=before['version']==after['version'],readback_verified=(sink.hash.hexdigest()==expected and before['version']==after['version'] and sink.bytes==int(after['size'])),
  numeric_verified=False,pit_verified=False,full_acceptance=False)
