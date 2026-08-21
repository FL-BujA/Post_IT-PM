# CONTRACT C1 — core (FROZEN after Phase 1 — changes only via a CC card)

core/ is pure Python: stdlib only, no DB, no IO, no framework imports.
Every other layer may import core. Nothing else may.

## C1.1 Enums (exact member values — API payloads use these strings)

```python
class ProjectStatus(str, Enum):
    CHARTER="charter"; ACTIVE="active"; IN_REVIEW="in_review"
    DELIVERED="delivered"; CLOSED="closed"

class EventKind(str, Enum):
    CHARTER="charter"; GATE="gate"; DECISION="decision"
    ACTION_CREATED="action_created"; ACTION_STATUS="action_status"
    EVIDENCE="evidence"; MEETING="meeting"; SIGNAL="signal"
    REPORT="report"; NOTE="note"; PHASE="phase"

class ActionStatus(str, Enum):
    OPEN="open"; IN_PROGRESS="in_progress"; DONE="done"
    DEFERRED="deferred"; CANCELLED="cancelled"

class GateOutcome(str, Enum):
    PLANNED="planned"; PASSED="passed"
    CONDITIONALLY_PASSED="conditionally_passed"; FAILED="failed"; SKIPPED="skipped"

class SourceType(str, Enum):
    EMAIL="email"; SPREADSHEET="spreadsheet"; SCREENSHOT="screenshot"
    DOC="doc"; OTHER="other"

class SignalKind(str, Enum):
    DEFER="defer"; EXTENSION_REQUEST="extension_request"
    LATE_START="late_start"; REOPEN="reopen"

# C1.1 addendum — the action state machine lives in core so BOTH the data
# layer and any future tooling validate transitions from one place:
ALLOWED_ACTION_TRANSITIONS: dict[ActionStatus, tuple[ActionStatus, ...]]
  # open        -> (in_progress, done, deferred, cancelled)
  # in_progress -> (done, deferred, cancelled, open)
  # done        -> (open,)                       # reopen: see invariant I4
  # deferred    -> (open, in_progress, cancelled)
  # cancelled   -> ()                            # terminal
# data/ActionRepo.set_status consults this dict; a missing target raises
# CoreError code "illegal_transition".
```

## C1.2 Value objects (dataclasses, frozen where noted)

- EventRef(ref_table: str, ref_id: int | None) — ref_table ∈
  {"actions","gates","minutes","evidence","reports"}; ref_id None only when
  ref_table None.
- EvidencePath(rel_path: str) — validated on construction (see C1.3).
- Owner(name: str) — normalized to trimmed, case-preserved string;
  non-empty (OwnerError otherwise).
- PreparedFor(value: str) — non-empty ("TBD" allowed by PM, empty not).

## C1.3 Path and slug rules (the glue rule, machine-enforceable)

- normalize_relpath(p: str) -> str
  - Must be relative (no drive, no leading "/"), no "..", no backslash runs
    that escape the workspace: backslashes are normalized to "/".
  - Must match one of:  evidence/<code>/<file>  |  reports/<code>/<file>
    where <code> matches ^P\d{3}[a-z]?$ and <file> matches
    ^\d{4}-\d{2}-\d{2}_[a-z0-9_]+(?:[A-Z][a-z]+)?\.[a-z0-9]+$  (evidence:
    date-prefixed files) — OR a second form for generated artifacts under
    reports (date-prefix required likewise).
  - Raises: InvalidSlug | PathEscape (both in C1.4).
- slugify(name: str, date: str, ext: str) -> "YYYY-MM-DD_slug.ext"
  - lowercases alphanumerics, runs of non-alnum become "_", trims "_",
    max 40 chars before ext, preserves extension case-insensitively.
  - slugify("") raises InvalidSlug. slugify("Bom (v3) - final", ...) ->
    "YYYY-MM-DD_bom_v3_final.ext".

## C1.4 Error types (base + hierarchy — imported by EVERY layer)

```python
class CoreError(Exception):
    def __init__(self, message: str, *, code: str): ...
    # code is a stable machine string, e.g. "invalid_slug"

class DataError(CoreError): ...          # data layer raises these
class ServiceError(CoreError): ...       # services layer raises these
# concrete:
class InvalidSlug(ServiceError): ...         # code "invalid_slug"
class PathEscape(ServiceError): ...          # code "path_escape"
class OwnerError(ServiceError): ...          # code "invalid_owner"
class UnknownProjectService(ServiceError): ...  # code "unknown_project"
class EvidenceConflict(ServiceError): ...  # code "evidence_conflict"
class GateMissing(ServiceError): ...       # code "gate_missing"
class CycleCloseError(ServiceError): ...   # code "cycle_close"
class IntegrityError(ServiceError): ...    # code "integrity"
class MissingFileError(ServiceError): ...  # code "missing_file"
class PdfError(ServiceError): ...          # code "pdf_error"
class UnknownProjectData(DataError): ...   # code "unknown_project"
```

## C1.5 Misc pure helpers

- now_utc() -> datetime (aware, tzinfo=UTC) — ALL timestamps produced via
  this function so the codebase cannot mix zones.
- sha256_file(path: str | os.PathLike) -> str   (hex lowercase)
- sha256_bytes(data: bytes) -> str
- short_id() -> str   # 8 hex chars from os.urandom, prefix "i" (internal ids
                       # for in-memory drafts only; persisted ids are SQLite ints)
- page_size_check helper: a4_page_pt = (595.27, 841.89)  # for renderer tests

Module layout (each ≤ 300 lines — R10): core/__init__.py re-exports the
public names below; core/enums.py, core/values.py, core/paths.py,
core/errors.py, core/time.py, core/hash.py.
Public API of core <= 7 public callables and types per module.
An exception hierarchy counts as one. Module-level constants and
compiled patterns are excluded from the count. (Surface rule,
distinct from the R10 size caps. Amended by CC-01.)
