"""core package surface tests (P-04, contract 01-CONTRACTS-core.md).

CC-01 (amended surface rule) counting model:
- A module's public surface = its public CALLABLES (functions / methods
  exposed at module level) and public TYPES (classes).
- An exception hierarchy counts as ONE surface item: every subclass of a
  public exception base is folded into the base's single entry.
- Module-level CONSTANTS (plain values such as frozen frozensets, ints,
  tuples, string constants) are EXCLUDED from the count.
- COMPILED PATTERNS (``re.Pattern`` instances, e.g. ``FILENAME_RE``) are
  EXCLUDED from the count.

``MAX_PUBLIC_PER_MODULE`` is therefore the ceiling on the count of
(callables + types-with-folded-exception-hierarchies) that any single
core source module may expose as public names.

Per-module ceiling (CC-01 amended).  Under the amended rule the surface
of each core module is small (a handful of callables/types each, with
``core.errors`` folding its 13 exception classes into one hierarchy
entry), so 7 comfortably contains every module while still bounding any
new module that a later card might introduce.
"""

from __future__ import annotations

import importlib
import os
import re
import types
import types as _types

import core
import core.enums
import core.errors
import core.hash
import core.paths
import core.time
import core.values

# ---------------------------------------------------------------------------
# CC-01 amended ceiling — see module docstring for the counting model.
# ---------------------------------------------------------------------------
MAX_PUBLIC_PER_MODULE = 7

# The six source modules of the core package (excluding the package's own
# ``__init__``, which re-exports the union of their public APIs).
SOURCE_MODULES = (
    "core.paths",
    "core.values",
    "core.enums",
    "core.errors",
    "core.time",
    "core.hash",
)


# ---------------------------------------------------------------------------
# CC-01 counting helpers
# ---------------------------------------------------------------------------
def _is_compiled_pattern(obj: object) -> bool:
    """True for compiled regex objects (the "compiled patterns" CC-01 excludes)."""
    return isinstance(obj, type(re.compile("x")))


def _is_module_level_constant(name: str, obj: object) -> bool:
    """True for module-level CONSTANTS (excluded by CC-01).

    A constant is a non-callable, non-type binding whose runtime type is a
    plain data type (str/int/float/bool/bytes/tuple/frozenset/set/list/dict).
    """
    if callable(obj) or isinstance(obj, type):
        return False
    if _is_compiled_pattern(obj):
        return False
    data_types = (
        str,
        int,
        float,
        bool,
        bytes,
        bytearray,
        tuple,
        list,
        set,
        frozenset,
        dict,
    )
    return isinstance(obj, data_types)


def _fold_exception_hierarchy(classes: set[type]) -> set[type]:
    """Collapse an exception hierarchy into its root(s).

    CC-01: "an exception hierarchy counts as one."  Every class that is a
    subclass of another exception class in the same set is folded into the
    topmost class, so a chain like ``CoreError → DataError →
    UnknownProjectData`` contributes a single surface entry (``CoreError``).
    """
    roots: set[type] = set()
    for cls in classes:
        subsumed_by_root = False
        for other in classes:
            if other is not cls and issubclass(cls, other) and issubclass(other, BaseException):
                subsumed_by_root = True
                break
        if not subsumed_by_root:
            roots.add(cls)
    return roots


def count_public_surface(module: types.ModuleType) -> int:
    """Count a module's public surface per the CC-01 amended rule.

    Public surface =
      (# public callables) + (# public types, with each exception
       hierarchy folded to a single entry).

    Module-level constants and compiled patterns are excluded.
    """
    names = set(getattr(module, "__all__", []))
    if not names:
        names = {
            n
            for n in dir(module)
            if not n.startswith("_")
            and not isinstance(getattr(module, n), (types.ModuleType, _types.ModuleType))
        }

    public: set[str] = set()
    unbound: set[str] = set()  # declared in __all__ but not bound — packaging drift
    for n in names:
        if n.startswith("_"):
            continue
        if not hasattr(module, n):
            unbound.add(n)
            continue
        obj = getattr(module, n)
        if isinstance(obj, types.ModuleType):
            continue  # re-exported sub-module, not part of this module's surface
        if _is_compiled_pattern(obj):
            continue  # compiled pattern — excluded by CC-01
        if _is_module_level_constant(n, obj):
            continue  # module-level constant — excluded by CC-01
        public.add(n)

    callables = {
        n for n in public if callable(getattr(module, n)) and not isinstance(getattr(module, n), type)
    }
    class_objs = {getattr(module, n) for n in public if isinstance(getattr(module, n), type)}

    return len(unbound) + len(callables) + len(_fold_exception_hierarchy(class_objs))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_import_core_exposes_contracts_api() -> None:
    """Every public name a source module declares in ``__all__`` is importable
    from the ``core`` package (the one surface, R10)."""
    all_names: set[str] = set()
    for name in SOURCE_MODULES:
        mod = importlib.import_module(name)
        all_names.update(getattr(mod, "__all__", []))

    missing = [n for n in sorted(all_names) if not hasattr(core, n)]
    assert not missing, f"names from source-module __all__ missing on core: {missing}"


def test_core_has_no_abs_path_attr() -> None:
    """Glue-rule insurance: no public attribute of ``core`` references an
    absolute path (a drive letter prefix such as ``D:\\``)."""
    bad: list[str] = []
    for name, obj in core.__dict__.items():
        if name.startswith("_"):
            continue
        if isinstance(obj, str):
            if re.search(r"[A-Za-z]:[\\/]", obj) or obj.startswith("/"):
                bad.append((name, obj))
    assert not bad, f"core attributes referencing absolute paths: {bad}"


def test_core_all_matches_reexports() -> None:
    """``core.__all__`` equals exactly the union of source-module public names,
    so the package's surface is closed and auditable (R10, P-04)."""
    all_names: set[str] = set()
    for name in SOURCE_MODULES:
        mod = importlib.import_module(name)
        all_names.update(getattr(mod, "__all__", []))

    assert set(core.__all__) == all_names, (
        f"core.__all__ drift: "
        f"extra={sorted(set(core.__all__) - all_names)} "
        f"missing={sorted(all_names - set(core.__all__))}"
    )


def test_public_surface_within_ceiling_per_module() -> None:
    """CC-01 amended: each source module's public surface (callables + types,
    exception hierarchy folded to one, constants and compiled patterns
    excluded) is ≤ ``MAX_PUBLIC_PER_MODULE``."""
    over: dict[str, int] = {}
    for name in SOURCE_MODULES:
        mod = importlib.import_module(name)
        n = count_public_surface(mod)
        if n > MAX_PUBLIC_PER_MODULE:
            over[name] = n
    assert not over, (
        f"modules over the {MAX_PUBLIC_PER_MODULE}-name public-surface ceiling "
        f"(CC-01 amended): {over}"
    )


def test_errors_hierarchy_folds_to_one() -> None:
    """CC-01: the ``core.errors`` exception hierarchy counts as ONE surface item.

    Under the amended rule the only public surface of ``core.errors`` is its
    single exception hierarchy (no public callables, no public types beyond
    the exception classes), so the folded count must be exactly 1.
    """
    mod = importlib.import_module("core.errors")
    assert count_public_surface(mod) == 1


def test_constants_and_compiled_patterns_excluded() -> None:
    """CC-01: module-level constants and compiled regex patterns are EXCLUDED
    from the public-surface count.

    Verify against ``core.paths`` — a module that exposes several constants
    (``ALLOWED_BUCKETS``, ``MAX_STEM_LEN``) and several compiled patterns
    (``DATE_RE``, ``STEM_RE``, ``SLUG_RE``, ``FILENAME_RE``,
    ``PROJECT_CODE_RE``).  The count must equal exactly the number of public
    callables (``slugify``, ``normalize_relpath``), not be inflated by the
    constants/patterns.
    """
    mod = importlib.import_module("core.paths")

    excluded = [
        n
        for n in mod.__all__
        if _is_module_level_constant(n, getattr(mod, n))
        or _is_compiled_pattern(getattr(mod, n))
    ]
    included = [
        n
        for n in mod.__all__
        if n not in excluded and callable(getattr(mod, n)) and not isinstance(getattr(mod, n), type)
    ]

    # The excluded set must actually contain the known constants/patterns,
    # and the surface count must match the callables only.
    assert "MAX_STEM_LEN" in excluded
    assert "ALLOWED_BUCKETS" in excluded
    assert "FILENAME_RE" in excluded
    assert set(included) == {"slugify", "normalize_relpath"}
    assert count_public_surface(mod) == len(included)


def test_sig_sheet_exists() -> None:
    """P-04: the signature sheet ``core.sig.txt`` exists (MOSAIC §6 artifact)."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sig_path = os.path.join(repo_root, "core.sig.txt")
    assert os.path.isfile(sig_path), f"signature sheet missing: {sig_path}"
