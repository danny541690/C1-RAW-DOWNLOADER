"""Real Drive immutable candidates. Only a fenced CAS receipt publishes them.

An interrupted upload may leave an orphan. Duplicate identical objects reconcile
by digest; conflicting values or corrupt bytes fail closed. No file is updated.
This first integration supports isolated test folders only.
"""
import hashlib
import io
import re

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload


class DriveImmutableArtifacts:
    requires_owner_fenced_store = True

    def __init__(self, api, parent, test_only=True):
        if test_only is not True:
            raise ValueError('PRODUCTION_DRIVE_BACKEND_NOT_ACTIVATED')
        meta = api.files().get(fileId=parent, fields='id,mimeType,appProperties').execute(num_retries=0)
        if meta.get('mimeType') != 'application/vnd.google-apps.folder' or meta.get('appProperties', {}).get('jarvis_stage06_scope') != 'ISOLATED_TEST_ONLY':
            raise ValueError('EXPLICIT_ISOLATED_FOLDER_REQUIRED')
        self.api, self.parent = api, parent
        self.verified = {}

    @staticmethod
    def _sha(raw):
        return hashlib.sha256(raw).hexdigest()

    def _objects(self, key):
        prefix = self._sha(key.encode()) + '-'
        query = "'" + self.parent.replace("'", "\\'") + "' in parents and trashed = false and name contains '" + prefix + "'"
        result = []; token = None
        while True:
            page = self.api.files().list(q=query, pageToken=token, pageSize=100,
                fields='nextPageToken,files(id,name)').execute(num_retries=0)
            for item in page.get('files', []):
                if not re.fullmatch(re.escape(prefix) + r'[0-9a-f]{64}\.artifact', item['name']):
                    raise ValueError('UNEXPECTED_ARTIFACT_NAME')
                result.append(item)
            token = page.get('nextPageToken')
            if not token:
                return result

    def _resolve(self, key):
        files = self._objects(key)
        if not files:
            return None
        hashes = {f['name'][-73:-9] for f in files}
        if len(hashes) != 1:
            raise ValueError('IMMUTABLE_DRIVE_KEY_CONFLICT')
        expected = next(iter(hashes)); payloads = []
        for item in sorted(files, key=lambda f: f['id']):
            raw = self.api.files().get_media(fileId=item['id']).execute(num_retries=0)
            if len(raw) > 32_000_000 or self._sha(raw) != expected:
                raise ValueError('DRIVE_ARTIFACT_READBACK_HASH_MISMATCH')
            payloads.append((item, raw))
        item, raw = payloads[0]
        self.verified[key] = dict(file_id=item['id'], parent_folder_id=self.parent, sha256=expected,
                                  logical_key_sha256=self._sha(key.encode()), backend='GOOGLE_DRIVE_IMMUTABLE_TEST')
        return raw

    def read(self, key):
        raw = self._resolve(key)
        if raw is None:
            raise FileNotFoundError('DRIVE_ARTIFACT_NOT_FOUND')
        return raw

    def put_immutable(self, key, raw, guard):
        if not isinstance(raw, bytes) or len(raw) > 32_000_000:
            raise ValueError('INVALID_ARTIFACT_BYTES')
        guard(); existing = self._resolve(key)
        if existing is not None:
            if existing != raw:
                raise ValueError('IMMUTABLE_DRIVE_KEY_CONFLICT')
            guard(); return
        guard()
        name = self._sha(key.encode()) + '-' + self._sha(raw) + '.artifact'
        try:
            self.api.files().create(body=dict(name=name, parents=[self.parent], appProperties={
                'jarvis_stage06_scope': 'ISOLATED_TEST_ONLY', 'publication': 'CANDIDATE_UNTIL_FENCED_RECEIPT'}),
                media_body=MediaIoBaseUpload(io.BytesIO(raw), mimetype='application/octet-stream', resumable=False),
                fields='id').execute(num_retries=0)
        except (OSError, HttpError) as exc:
            status = getattr(getattr(exc, 'resp', None), 'status', None)
            if isinstance(exc, HttpError) and status not in (408, 429, 500, 502, 503, 504):
                raise
            # Reconcile an ambiguous create; never blindly repeat the upload.
            if self._resolve(key) != raw:
                raise
        guard()
        if self._resolve(key) != raw:
            raise ValueError('DRIVE_ARTIFACT_READBACK_HASH_MISMATCH')
        guard()

    def private_reference(self, key):
        # Full IDs are stored only in the private Drive validation object.
        return dict(self.verified[key])

    def reference(self, key):
        return {k: v for k, v in self.verified[key].items() if k not in ('file_id', 'parent_folder_id')}
