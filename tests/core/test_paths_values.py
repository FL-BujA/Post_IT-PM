"""Tests for core.paths (C1.2) and core.values (C1.3) — card P-02.

Done-when (P-02, verbatim from the card):
  - slugify("Bom (v3) - final", date, ext) == "<date>_bom_v3_final.<ext>"
    (exact test from contract), plus: empty raises InvalidSlug; 100-char
    stem truncates to 40; unicode -> ascii-safe.
  - normalize_relpath PASS cases (exact) and FAIL cases with the EXACT
    exception class + .code asserted.
  - Owner("  ana  ") == Owner("ana"); Owner("") raises OwnerError.
  - PreparedFor("") raises; PreparedFor("TBD") ok.
  - EventRef: ref_table None implies ref_id None; ref_table must be in
    the frozen 5-table set.
"""

from __future__ import annotations

import pytest

from core.enums import EventKind
from core.errors import InvalidSlug, OwnerError, PathEscape
from core.paths import ALLOWED_BUCKETS, MAX_STEM_LEN, normalize_relpath, slugify
from core.values import ALLOWED_REF_TABLES, EventRef, Owner, PreparedFor


# --- slugify (C1.2) -------------------------------------------------------


def test_slugify_exact_contract_example() -> None:
    date = "2026-08-20"
    ext = "xlsx"
    assert slugify("Bom (v3) - final", date, ext) == "2026-08-20_bom_v3_final.xlsx"
    # exact template form with other values
    assert slugify("Bom (v3) - final", date, ext) == f"{date}_bom_v3_final.{ext}"


def test_slugify_is_pure_string_in_out() -> None:
    result = slugify("Bom (v3) - final", "2026-08-20", "xlsx")
    assert isinstance(result, str)
    assert "\\" not in result
    assert " " not in result


def test_slugify_empty_name_raises_invalid_slug() -> None:
    with pytest.raises(InvalidSlug) as exc:
        slugify("", "2026-08-20", "xlsx")
    assert exc.value.code == "invalid_slug"
    with pytest.raises(InvalidSlug):
        slugify("   ", "2026-08-20", "xlsx")


def test_slugify_100char_stem_truncates_to_40() -> None:
    long_name = "a" * 100
    result = slugify(long_name, "2026-08-20", "xlsx")
    stem = result.split("_", 1)[1].split(".")[0]
    assert len(stem) == 40 == MAX_STEM_LEN
    assert result == "2026-08-20_" + "a" * 40 + ".xlsx"


def test_slugify_long_stem_with_separators_truncates_to_40() -> None:
    name = "x" * 30 + "-" + "y" * 100
    result = slugify(name, "2026-08-20", "xlsx")
    stem = result.split("_", 1)[1].split(".")[0]
    assert len(stem) == 40


def test_slugify_unicode_transliterates_to_ascii_safe() -> None:
    result = slugify("Über-Fähre", "2026-08-20", "pdf")
    assert result == "2026-08-20_uber_fahre.pdf"
    assert all(ord(c) < 128 for c in result)


def test_slugify_invalid_date_raises_invalid_slug() -> None:
    for bad_date in ("", "2026-08-20x", "26-08-20", "2026-13-01", "2026-01-32"):
        with pytest.raises(InvalidSlug):
            slugify("Bom (v3) - final", bad_date, "xlsx")


def test_slugify_invalid_extension_raises_invalid_slug() -> None:
    for bad_ext in ("", "x y", "a/b", "a.b"):
        with pytest.raises(InvalidSlug):
            slugify("Bom (v3) - final", "2026-08-20", bad_ext)


def test_slugify_name_without_ascii_chars_raises_invalid_slug() -> None:
    with pytest.raises(InvalidSlug) as exc:
        slugify("（全角括号）", "2026-08-20", "xlsx")
    assert exc.value.code == "invalid_slug"


# --- normalize_relpath (C1.2) --------------------------------------------


@pytest.mark.parametrize(
    "relpath",
    [
        "evidence/P001/2026-07-14_bom.xlsx",
        "reports/P001/2026-08-05_report.html",
    ],
)
def test_normalize_relpath_pass_cases_are_exact(relpath: str) -> None:
    assert normalize_relpath(relpath) == relpath


def test_normalize_relpath_rejects_backslash_escape() -> None:
    with pytest.raises(PathEscape) as exc:
        normalize_relpath("evidence\\P001\\2026-07-14_bom.xlsx")
    assert exc.value.code == "path_escape"


def test_normalize_relpath_rejects_traversal() -> None:
    with pytest.raises(PathEscape) as exc:
        normalize_relpath("../x")
    assert exc.value.code == "path_escape"


def test_normalize_relpath_rejects_drive_prefix() -> None:
    with pytest.raises(PathEscape) as exc:
        normalize_relpath("C:/x")
    assert exc.value.code == "path_escape"


def test_normalize_relpath_rejects_absolute_path() -> None:
    with pytest.raises(PathEscape) as exc:
        normalize_relpath("/x")
    assert exc.value.code == "path_escape"


def test_normalize_relpath_bad_project_code_is_invalid_slug() -> None:
    with pytest.raises(InvalidSlug) as exc:
        normalize_relpath("evidence/P9/2026-01-01_a.pdf")
    assert exc.value.code == "invalid_slug"


def test_normalize_relpath_missing_date_prefix_is_invalid_slug() -> None:
    with pytest.raises(InvalidSlug) as exc:
        normalize_relpath("evidence/P001/no_date.pdf")
    assert exc.value.code == "invalid_slug"


def test_normalize_relpath_unknown_bucket_is_invalid_slug() -> None:
    with pytest.raises(InvalidSlug):
        normalize_relpath("bogus/P001/2026-01-01_a.pdf")


def test_normalize_relpath_rejects_empty_and_traversal_segments() -> None:
    for bad in ("", "evidence//2026-01-01_a.pdf", "evidence/P001/../a.xlsx"):
        with pytest.raises((PathEscape, InvalidSlug)):
            normalize_relpath(bad)


def test_allowed_buckets_is_the_frozen_five() -> None:
    assert ALLOWED_BUCKETS == frozenset(
        {"evidence", "attachments", "minutes", "reports", "exports"}
    )


# --- Owner (C1.3) ----------------------------------------------------------


def test_owner_strips_whitespace_and_compares_by_value() -> None:
    assert Owner("  ana  ") == Owner("ana")
    assert Owner("  ana  ").name == "ana"
    assert Owner("ana") == Owner(" ana\n")


def test_owner_empty_raises_owner_error() -> None:
    with pytest.raises(OwnerError) as exc:
        Owner("")
    assert exc.value.code == "invalid_owner"
    with pytest.raises(OwnerError):
        Owner("   ")


def test_owner_preserves_inner_whitespace() -> None:
    assert Owner("ana  maria").name == "ana  maria"


# --- PreparedFor (C1.3) ----------------------------------------------------


def test_prepared_for_empty_raises() -> None:
    with pytest.raises(OwnerError) as exc:
        PreparedFor("")
    assert exc.value.code == "invalid_owner"
    with pytest.raises(OwnerError):
        PreparedFor("   ")


def test_prepared_for_tbd_is_ok() -> None:
    assert PreparedFor("TBD").value == "TBD"


def test_prepared_for_strips_and_compares_by_value() -> None:
    assert PreparedFor("  Acme Inc  ") == PreparedFor("Acme Inc")


# --- EventRef (C1.3) -------------------------------------------------------


def test_event_ref_none_pairs_round_trip() -> None:
    ref = EventRef(EventKind.NOTE, None, None)
    assert ref.ref_table is None
    assert ref.ref_id is None
    assert EventRef(EventKind.NOTE, "decision", 42).ref_table == "decision"


def test_event_ref_constructor_enforces_none_pairing() -> None:
    with pytest.raises(OwnerError):
        EventRef(EventKind.NOTE, None, 7)
    with pytest.raises(OwnerError):
        EventRef(EventKind.NOTE, "decision", None)


def test_event_ref_table_must_be_in_frozen_five_set() -> None:
    assert ALLOWED_REF_TABLES == frozenset(
        {"charter", "decision", "action", "meeting", "gate"}
    )
    for table in ALLOWED_REF_TABLES:
        EventRef(EventKind.GATE, table, 1)
    with pytest.raises(OwnerError) as exc:
        EventRef(EventKind.GATE, "bogus_table", 1)
    assert exc.value.code == "invalid_owner"


def test_event_ref_rejects_non_event_kind() -> None:
    with pytest.raises(TypeError):
        EventRef("note", None, None)
