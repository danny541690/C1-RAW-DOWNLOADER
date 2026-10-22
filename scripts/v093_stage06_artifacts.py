"""Atomic immutable local staging backend; authority remains in the CAS ledger."""
import fcntl
import hashlib
import os
import tempfile
from pathlib import Path


class LocalImmutableArtifacts:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + '.artifact')

    def read(self, key):
        return self.path(key).read_bytes()

    def put_immutable(self, key, raw, guard):
        if not isinstance(raw, bytes):
            raise ValueError('ARTIFACT_MUST_BE_BYTES')
        with open(self.root / 'WRITE.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            guard()
            target = self.path(key)
            if target.exists():
                if target.read_bytes() != raw:
                    raise ValueError('IMMUTABLE_ARTIFACT_CONFLICT')
                return
            fd, temporary = tempfile.mkstemp(dir=self.root, prefix='pending-')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                guard()
                os.link(temporary, target)
                directory = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                os.unlink(temporary)
