"""core.hash — evidence integrity hashes and page geometry (C1.5).

Property: core NEVER diverges from the stdlib. ``sha256_bytes`` and
``sha256_file`` are exact delegations to ``hashlib.sha256`` — the same
bytes in, the same hex digest out. File hashing is streaming (64 KiB
chunks) so multi-gigabyte evidence files cost constant memory.
"""

from __future__ import annotations

import hashlib
import os

__all__ = ["A4_PAGE_PT", "SHORT_ID_LEN", "sha256_bytes", "sha256_file", "short_id"]

#: A4 page size in PDF points (595 x 842) — frozen (C1.5).
A4_PAGE_PT = (595, 842)

#: Total length of an evidence row id from ``short_id()``.
SHORT_ID_LEN = 9

_CHUNK_SIZE = 64 * 1024


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of ``data`` — exact stdlib equality (C1.5)."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike) -> str:
    """Hex SHA-256 of a file, streamed in 64 KiB chunks (C1.5).

    Same digest as feeding the whole file to ``hashlib.sha256``; works
    on 0-byte files and arbitrarily large ones.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short_id() -> str:
    """A new evidence row id (C1.5).

    ``"i"`` + 8 lowercase hex chars: 9 chars total, starts with "i",
    hex tail, and two calls differ (128 bits of randomness behind the
    tail).
    """
    return "i" + os.urandom(4).hex()
