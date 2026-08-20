"""Tests for core.time (C1.5) and core.hash (C1.5) — card P-03.

Done-when (P-03, verbatim from the card):
  - now_utc() returns aware datetime; tzinfo UTC, and two calls 50 ms
    apart: second >= first (no regression, no zone drift).
  - sha256_bytes("hello".encode()) == hashlib.sha256("hello".encode())
    .hexdigest() (exact stdlib equality — core NEVER diverges from
    hashlib).
  - sha256_file: write a 0-byte file and a 50 MB random file (seeded
    os.urandom chunked), assert both match a streaming hashlib reference
    computed in the test.
  - short_id(): starts "i", 9 chars total, hex tail, two calls differ.
  - a4_page_pt constant present with frozen values.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime, timezone

from core.hash import A4_PAGE_PT, SHORT_ID_LEN, sha256_bytes, sha256_file, short_id
from core.time import now_utc

FIFTY_MB = 50 * 1024 * 1024
CHUNK = 1024 * 1024


# --- now_utc (C1.5) -------------------------------------------------------


def test_now_utc_is_aware_and_utc() -> None:
    now = now_utc()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(now)
    assert now.tzinfo == timezone.utc


def test_now_utc_two_calls_50ms_apart_do_not_regress() -> None:
    first = now_utc()
    time.sleep(0.05)
    second = now_utc()
    assert second >= first
    assert second.tzinfo is not None


# --- sha256_bytes (C1.5) --------------------------------------------------


def test_sha256_bytes_exact_stdlib_equality_hello() -> None:
    data = "hello".encode()
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_sha256_bytes_exact_stdlib_equality_empty() -> None:
    assert sha256_bytes(b"") == hashlib.sha256(b"").hexdigest()


def test_sha256_bytes_exact_stdlib_equality_random() -> None:
    data = os.urandom(4096)
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


# --- sha256_file (C1.5) ---------------------------------------------------


def _streaming_reference(path: str) -> str:
    """The card's reference: streaming hashlib computed in the test."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_sha256_file_zero_byte_matches_streaming_reference(tmp_path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    assert sha256_file(str(path)) == _streaming_reference(str(path))
    assert sha256_file(str(path)) == hashlib.sha256(b"").hexdigest()


def test_sha256_file_50mb_random_matches_streaming_reference(tmp_path) -> None:
    path = tmp_path / "big.bin"
    with open(path, "wb") as fh:
        written = 0
        while written < FIFTY_MB:
            chunk = os.urandom(min(CHUNK, FIFTY_MB - written))
            fh.write(chunk)
            written += len(chunk)
    assert os.path.getsize(path) == FIFTY_MB
    assert sha256_file(str(path)) == _streaming_reference(str(path))


# --- short_id (C1.5) ------------------------------------------------------


def test_short_id_starts_i_and_is_9_chars_hex_tail() -> None:
    value = short_id()
    assert isinstance(value, str)
    assert value.startswith("i")
    assert len(value) == 9 == SHORT_ID_LEN
    assert re.fullmatch(r"i[0-9a-f]{8}", value)


def test_short_id_two_calls_differ() -> None:
    assert short_id() != short_id()


# --- A4_PAGE_PT (C1.5) ----------------------------------------------------


def test_a4_page_pt_constant_is_frozen_values() -> None:
    assert A4_PAGE_PT == (595, 842)
    assert len(A4_PAGE_PT) == 2
    assert A4_PAGE_PT[0] == 595
    assert A4_PAGE_PT[1] == 842
