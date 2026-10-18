"""Byte-level persistence verifier, backend-neutral and offline-testable.

A real Google Drive backend must implement write_bytes(path, data) and
read_bytes(path); this module is NOT itself a Drive connector.
"""
import hashlib

def sha256(data):
    if not isinstance(data, bytes):
        raise TypeError("native response must be bytes")
    return hashlib.sha256(data).hexdigest()

def persist_verified(storage, path, data):
    """Return receipt only after remote readback matches exact native bytes."""
    expected = sha256(data)
    storage.write_bytes(path, data)
    actual = storage.read_bytes(path)
    if not isinstance(actual, bytes) or len(actual) != len(data) or sha256(actual) != expected:
        raise ValueError("PERSISTENCE_READBACK_MISMATCH")
    return {"path": path, "sha256": expected, "bytes": len(data), "readback_verified": True}

class MemoryStorage:
    """TEST FAKE ONLY; not persistent, not Google Drive."""
    def __init__(self):
        self.files = {}
    def write_bytes(self, path, data):
        self.files[path] = data
    def read_bytes(self, path):
        return self.files[path]
