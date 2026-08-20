"""core.paths — slug, date, and relative-path rules (contract C1.2).

Glue rule: the relative path string IS the stored form. These helpers are
pure string in / string out — no ``pathlib.Path`` anywhere in this module —
and they are the ONLY place validation of stored paths happens. Later
layers call them; they never re-implement the rules.

Rules (C1.2):
- filename  = ``<YYYY-MM-DD>_<stem>.<ext>`` with stem <= 40 chars
- stem      = ``[a-z0-9_]+`` (ascii, no dots, no backslashes)
- date      = ``YYYY-MM-DD`` with a real calendar month and day
- relpath   = 2 or 3 forward-slash segments:
  ``<bucket>/<project>/<filename>`` where
  bucket    = one of the 5 frozen table buckets (evidence, attachments,
              minutes, reports, exports)
  project   = ``P\\d{3}``
- Windows drive prefixes (``C:``) and absolute paths (``/x``) are escapes.
"""

from __future__ import annotations

import re
import unicodedata

from core.errors import InvalidSlug, PathEscape

__all__ = [
    "ALLOWED_BUCKETS",
    "DATE_RE",
    "FILENAME_RE",
    "MAX_STEM_LEN",
    "normalize_relpath",
    "PROJECT_CODE_RE",
    "slugify",
    "SLUG_RE",
    "STEM_RE",
]

#: Frozen set of path buckets — one per table that stores files (C1.2).
ALLOWED_BUCKETS: frozenset[str] = frozenset(
    {"evidence", "attachments", "minutes", "reports", "exports"}
)

MAX_STEM_LEN = 40

# Frozen regexes. Note: no character class anywhere accepts a backslash.
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
STEM_RE = re.compile(r"[a-z0-9_]+\Z")
SLUG_RE = re.compile(r"[a-z0-9_]+\Z")
FILENAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}_[a-z0-9_]{1,40}\.[a-z0-9]{1,15}\Z")
PROJECT_CODE_RE = re.compile(r"P[0-9]{3}\Z")


def _valid_date(date: str) -> bool:
    """True if ``date`` is ``YYYY-MM-DD`` with a real month and day."""
    if len(date) != 10 or date[4] != "-" or date[7] != "-":
        return False
    month = int(date[5:7])
    day = int(date[8:10])
    return 1 <= month <= 12 and 1 <= day <= 31


def slugify(name: str, date: str, ext: str) -> str:
    """Build a stored filename ``<date>_<stem>.<ext>`` (C1.2).

    - ``date`` must be ``YYYY-MM-DD`` with a real month/day, else
      ``InvalidSlug``.
    - ``name`` is transliterated to ascii, lowercased, non-alnum runs
      collapsed to ``_``, stripped of ``_``; an empty stem is
      ``InvalidSlug``; a > 40-char stem is truncated to 40.
    - ``ext`` must be ascii ``[a-z0-9]`` without dots; empty is
      ``InvalidSlug``.

    Returns the plain string form — this exact string is what the DB
    stores.
    """
    if not DATE_RE.match(date) or not _valid_date(date):
        raise InvalidSlug(f"invalid date prefix: {date!r}")

    if ext is None or not ext or not re.fullmatch(r"[a-z0-9]{1,15}", ext):
        raise InvalidSlug(f"invalid extension: {ext!r}")

    if name is None or not name.strip():
        raise InvalidSlug("empty name: cannot build a slug")

    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = "".join(c for c in normalized if ord(c) < 128)
    lowered = ascii_text.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")

    if not collapsed:
        raise InvalidSlug("name does not contain any slug-usable characters")

    if len(collapsed) > MAX_STEM_LEN:
        collapsed = collapsed[:MAX_STEM_LEN].rstrip("_")

    return f"{date}_{collapsed}.{ext}"


def normalize_relpath(relpath: str) -> str:
    """Validate and canonicalize a stored relative path (C1.2).

    Returns the path unchanged (it is already the stored form) if it is
    exactly 2 or 3 forward-slash segments:

        bucket / project / filename

    with ``bucket`` in the frozen 5-bucket set, ``project`` matching
    ``P\\d{3}``, and ``filename`` matching ``<YYYY-MM-DD>_<stem>.<ext>``
    with a valid calendar date and a valid slug (else ``InvalidSlug``).

    Escapes — drive prefixes (``C:/x``), absolute paths (``/x``),
    backslashes, ``..``, empty segments — raise ``PathEscape``.
    """
    if not isinstance(relpath, str) or not relpath:
        raise PathEscape("empty relative path")

    # Escapes first: backslashes, drive letters, absolute paths, traversal.
    if "\\" in relpath or "://" in relpath:
        raise PathEscape(f"forbidden path form: {relpath!r}")
    if re.match(r"^[A-Za-z]:", relpath):
        raise PathEscape(f"absolute (drive) path: {relpath!r}")
    if relpath.startswith("/"):
        raise PathEscape(f"absolute path: {relpath!r}")

    parts = relpath.split("/")
    if any(part == "" for part in parts):
        raise PathEscape(f"empty path segment: {relpath!r}")
    if any(part == ".." or part == "." for part in parts):
        raise PathEscape(f"traversal segment: {relpath!r}")
    if not (2 <= len(parts) <= 3):
        raise PathEscape(f"expected 2-3 segments, got {len(parts)}: {relpath!r}")

    bucket = parts[0]
    if bucket not in ALLOWED_BUCKETS:
        raise InvalidSlug(f"unknown bucket: {bucket!r}")

    if len(parts) == 2:
        return relpath

    project, filename = parts[1], parts[2]
    if not PROJECT_CODE_RE.match(project):
        raise InvalidSlug(f"invalid project code: {project!r}")

    date_part, rest = filename.split("_", 1)
    if not DATE_RE.match(date_part) or not _valid_date(date_part):
        raise InvalidSlug(f"filename missing valid date prefix: {filename!r}")
    stem, dot, ext = rest.rpartition(".")
    if not dot or not stem or not STEM_RE.match(stem) or not SLUG_RE.match(ext):
        raise InvalidSlug(f"invalid slug in filename: {filename!r}")

    return relpath
