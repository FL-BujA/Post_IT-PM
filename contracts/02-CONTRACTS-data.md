# CONTRACT C2 — data (FROZEN after Phase 1 — changes only via a CC card)

data/ owns SQLite only. It imports core (types/errors) and stdlib sqlite3.
It NEVER imports services/api. Its one public entry is the DataKit
(see C2.1). Repositories are separate classes, one per aggregate, all
constructed with the shared connection (single connection pool of 1 —
architecture §7).

## C2.0 Row schemas (stored forms — API-facing shapes in C3/C4)

projects(id int PK, code text UNIQUE check ^P\d{3}[a-z]?$, name, sponsor,
 target_date date NULL, status text check in enum, charter_text, objective,
 constraints_text, created_at)
timeline_events(id PK, project_id -> projects.id, kind text, title, summary,
 occurred_at, entered_at, ref_table text NULL, ref_id int NULL)
cycles(id PK, project_id, name, opened_at, closed_at NULL,
 gate_id -> gates.id NULL)
gates(id PK, project_id, name, planned_date NULL, actual_date NULL,
 outcome text NULL check in enum, exit_criteria, notes)
actions(id PK, project_id, cycle_id -> cycles.id NULL, title, owner,
 description, priority int check 1..9 default 9, due_start NULL, due_end NULL,
 started_at NULL, closed_at NULL, status text, reopen_count int default 0,
 last_reopened_at NULL)
evidence(id PK, project_id, rel_path text UNIQUE, sha256, size, mime,
 source_type text, note, attached_at, attached_by default 'pm')
meeting_minutes(id PK, project_id, cycle_id NULL, held_at, attendees,
 decisions, agreed_actions, risks, minutes_text)
engagement_signals(id PK, project_id, owner, kind text, action_id NULL,
 occurred_at, note, resolved bool default 0, resolved_at NULL)
report_history(id PK, project_id, generated_at, pdf_rel_path, html_rel_path,
 prepared_for, snapshot_sha256)
meta(key PK, value)   -- schema_version, workspace_root, last_backup_at
FTS5 table fts_search over meeting_minutes.minutes_text, evidence.note,
 timeline_events.summary (content-sync triggers per table).

## C2.1 The DataKit (the ONLY thing services/ may call)

```python
class DataKit:
    def __init__(self, db_path: str): ...           # opens, WAL, busy_timeout
    def close(self) -> None: ...
    def tx(self, fn) -> T: ...
    # tx(fn): runs fn inside one transaction; commits on return, rolls back
    # on ANY exception. All mutating methods below are wrapped in tx by the
    # caller (services) — repositories are transaction-free internally.

    projects:     ProjectRepo
    events:       EventRepo
    cycles:       CycleRepo
    gates:        GateRepo
    actions:      ActionRepo
    evidence:     EvidenceRepo
    minutes:      MinutesRepo
    signals:      SignalRepo
    reports:      ReportHistoryRepo
    search:       SearchRepo
    integrity:    IntegrityService            # in data layer (I2 lives here)
```

## C2.2 Repositories (exact method signatures)

ProjectRepo
  create(code,name,sponsor,target_date,status,objective) -> int (id)
  get(project_id) -> ProjectRow          # raises UnknownProjectData
  get_by_code(code) -> ProjectRow
  list(status: ProjectStatus | None = None) -> list[ProjectRow]
  set_status(project_id, status) -> None
  set_sponsor(project_id, sponsor) -> None      # the "prepared for" source

EventRepo
  emit(kind: EventKind, project_id, title, summary="",
       occurred_at=None, ref_table=None, ref_id=None) -> int
  list_for(project_code, kind=None, limit=200) -> list[EventRow]
      # ORDER BY occurred_at ASC, id ASC

CycleRepo
  open(project_id, name) -> int
  close(cycle_id, gate_row: GateRow) -> None
      # INvariant I3: raises GateMissing if gate_row.outcome is None (i.e.
      # PLANNED) or gate belongs to another project; then sets closed_at,
      # links gate_id, emits gate event (kind GATE, ref gates/gate id).
  current_for(project_id) -> CycleRow | None   # the open one, else None

GateRepo
  create(project_id, name, planned_date=None, exit_criteria="", notes="") -> int
  record_outcome(gate_id, outcome: GateOutcome, actual_date=None) -> None
      # emits gate event (kind GATE, ref gates/gate id)
  get(gate_id) -> GateRow; list_for(project_id) -> list[GateRow]

ActionRepo
  create(project_id, cycle_id, title, owner, description="",
         priority=9, due_start=None, due_end=None) -> int
      # emits event ACTION_CREATED (ref actions/id) on creation
  set_status(action_id, new: ActionStatus) -> None
      # emits event ACTION_STATUS; enforces I4:
      #   done->open: reopen_count += 1, last_reopened_at=now, and
      #     signals.insert(kind=REOPEN, action_id=action_id, owner=owner)
      #   started_at set on first open|done->in_progress
      #   closed_at set on done|deferred|cancelled
      # illegal transitions (e.g. cancelled->done) raise CoreError with
      # code "illegal_transition". The allowed set is
      # ALLOWED_ACTION_TRANSITIONS (defined in core/enums.py, C1.1 addendum).
  get(action_id) -> ActionRow; list_for(project_id, cycle_id=None) -> list[ActionRow]

EvidenceRepo
  record(row: EvidenceRow) -> int      # raises EvidenceConflict on rel_path dup
  list_for(project_code) -> list[EvidenceRow]
  get_by_path(rel_path) -> EvidenceRow

MinutesRepo
  add(project_id, held_at, attendees, decisions, agreed_actions, risks,
      minutes_text, cycle_id=None) -> int
      # emits event MEETING (ref minutes/id)
  list_for(project_id) -> list[MinutesRow]

SignalRepo
  insert(kind: SignalKind, project_id, owner, action_id=None, note="") -> int
      # emits event SIGNAL (ref signals not in ref_table set — see note)
  list_for(project_code, kind=None, owner=None, resolved=None) -> list[SignalRow]
  set_resolved(signal_id, resolved: bool) -> None
  NOTE: ref_table allowed set in C1.2 does NOT include "signals"; SIGNAL
  events carry ref_table=NULL. (Frozen: keep it simple — event summary text
  carries the signal id, e.g. "Signal #12: extension_request (owner Ana)".)

ReportHistoryRepo
  add(project_id, pdf_rel_path, html_rel_path, prepared_for,
      snapshot_sha256, generated_at=None) -> int
      # emits event REPORT (ref reports/id)
  list_for(project_code) -> list[ReportRow]

SearchRepo
  search(terms: str, project_code: str | None = None,
         limit: int = 50) -> list[Hit]
      # Hit(table: str, row_id: int, snippet: str)  — table in
      # {"minutes","evidence","events"}; FTS5 match; order: relevance desc,
      # then occurred_at desc. Raises CoreError code "fts_unavailable" only
      # if the FTS table is missing (migration bug — should never happen).

IntegrityService   (lives in data because it reads both db + disk)
  verify(workspace_root: str) -> IntegrityReport
      # IntegrityReport(ok: bool,
      #                 missing: list[EvidenceRow],     # row, no file  (I2)
      #                 mismatched: list[tuple[EvidenceRow, str]],  # hash fail
      #                 orphans: list[str])              # file, no row (rel paths)
      # Never deletes. Pure read.

## C2.3 Row dataclasses (data/rows.py, one dataclass per table, fields =
## C2.0 columns, all typed; to_dict() for json; no methods beyond that).

## C2.4 Migration (data/migrate.py)
  SCHEMA_VERSION = 1
  migrate(db_path) -> int
  - creates tables, indexes (timeline_events(project_id, occurred_at),
    actions(project_id, status, priority), evidence(project_id), unique
    evidence(rel_path), signals(project_id, owner)), FTS5 table + triggers,
    seeds meta.schema_version='1'.
  - Idempotent: safe to run on an existing v1 db (IF NOT EXISTS everywhere;
    version check skips DDL, still returns 1).
  - WAL mode + busy_timeout(5000) set on the connection in DataKit.__init__.

## C2.5 Stubs (app/stubs/data.py implements the SAME signatures, canned data)
  - 2 canned projects: P001 "Alpha (canned)" (ACTIVE, sponsor "Sponsor A",
    target_date 2026-09-30) and P002 "Beta (canned)" (CHARTER, sponsor None).
  - Canned events/actions/cycle/gate per project: at least one open cycle,
    3 actions (one of each: OPEN prio1 owner "Ana", IN_PROGRESS prio2 owner
    "Ben", DONE prio3 owner "Ana"), 1 gate PLANNED, 1 evidence rel_path
    "evidence/P001/2026-08-01_canned.pdf" (file deliberately absent — verify()
    must report it missing; that is correct stub behavior), 1 minutes row,
    2 signals (extension_request Ana, late_start Ben).
  - verify() stub returns IntegrityReport(ok=False, missing=<that one>) —
    deterministic so tests are stable.
