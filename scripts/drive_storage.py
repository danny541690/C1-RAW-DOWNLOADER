"""Google Drive backend contract. Requires explicit authenticated Drive service.

Never put service-account secrets in the public repository. The Github runner
is not authorized by a user's separate ChatGPT Google Drive connector.
"""
import hashlib
import io
from scripts.storage_verifier import persist_verified

class GoogleDriveStorage:
    def __init__(self, service, parent_folder_id):
        self.service=service
        self.parent=parent_folder_id

    def _find(self,name):
        escaped=name.replace("\\","\\\\").replace("'","\\'")
        q=f"name = '{escaped}' and '{self.parent}' in parents and trashed = false"
        result=self.service.files().list(q=q,fields="files(id,name,mimeType),nextPageToken",page_size=100).execute()
        files=result.get("files",[])
        if len(files)>1: raise ValueError("duplicate Drive file names")
        return files[0]["id"] if files else None

    def write_bytes(self,name,data):
        from googleapiclient.http import MediaIoBaseUpload
        media=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/octet-stream",resumable=True)
        file_id=self._find(name)
        if file_id:
            self.service.files().update(fileId=file_id,media_body=media,fields="id").execute()
        else:
            self.service.files().create(body={"name":name,"parents":[self.parent]},
                media_body=media,fields="id").execute()

    def read_bytes(self,name):
        file_id=self._find(name)
        if not file_id: raise FileNotFoundError(name)
        return self.service.files().get_media(fileId=file_id).execute()

def verify_drive_unit(storage,name,data):
    return persist_verified(storage,name,data)
