# CONTRACT C3 — services (FROZEN after Phase 1 — changes only via a CC card)

services/ = use cases. Imports core (types/errors) and data (DataKit, rows).
NEVER imports api/app. Every method that mutates state runs inside
DataKit.tx(...) at the service level (one logical unit = one transaction).

All services receive their DataKit via the ServiceKit (C3.1) — no global
state, no module-level DB handles. This is what makes the composition root
(a pure swap of implementations) possible.

## C3.1 The ServiceKit (the ONLY thing api/ may call)

```python
class ServiceKit:
    def __init__(self, data: DataKit, renderer: Renderer,
                 workspace_root: str): ...
    evidence:    EvidenceService
    flow:        FlowService
    engagement:  EngagementService
    report:      ReportService
    backup:      BackupService
    handover:    HandoverService
    @property
    def data(self) -> DataKit: ...        # exposed read-only for api queries
```

Renderer is the one seam whose "real" implementation needs a third-party
renderer; it is a contract (C3.6) so the stub/real swap stays in the
composition root (anti-pattern #9: stub data must never leak past the root).

## C3.2 EvidenceService

```python
class EvidenceService:
    def attach(self, project_code: str, source_path: str,
               source_type: SourceType, note: str = "") -> EvidenceRow:
        """Copy source_path into evidence/<code>/<date>_<slug>.<ext>,
        compute sha256, persist glue row, emit the evidence event.
        source_path is any readable local file (PM's Downloads, etc.).
        Raises: UnknownProjectService, EvidenceConflict (rel_path exists),
                InvalidSlug, MissingFileError (source_path unreadable).
        Never raises for a file > 200 MB (personal tool; no cap enforced)."""

    def open_path(self, project_code: str, rel_path: str) -> str:
        """Return the ABSOLUTE path of an evidence file after validating
        rel_path + project + existence. Raises PathEscape, MissingFileError.
        (The API layer never exposes absolute paths in responses — this
        helper exists for the ui 'open in Explorer' intent and tests.)"""

    def list_for(self, project_code: str) -> list[EvidenceRow]: ...
```

Guarantees (frozen): the destination filename is produced by core.slugify
from the SOURCE's date (file mtime) + stem + extension; a collision (same
name already in evidence/) appends _2, _3 ... BEFORE storing, and the stored
rel_path is what the row carries (row always = truth of where the file is).

## C3.3 FlowService (cycle / gate / action orchestration)

```python
class FlowService:
    def create_project(self, name, sponsor, target_date, objective,
                       charter_text="", constraints_text="") -> ProjectRow:
        """Allocates next code P00x (sequence from existing projects, zero-
        padded, suffix 'a' on year rollover is NOT needed for 12 days —
        next free code = max existing + 1, formatted P%03d).
        Status=CHARTER. Emits charter event (kind CHARTER, ref_table None).
        Raises: OwnerError if sponsor empty AND not 'TBD' — no: sponsor may
        be None (open field per scope); charter event title =
        'Charter drafted: <name>'."""

    def open_cycle(self, project_code: str, name: str) -> CycleRow:
        """Only one open cycle per project; a second while one is open
        raises ServiceError code 'cycle_open' (frozen rule: close the old
        one first — the loop does not overlap for v1). Emits phase event
        (kind PHASE, title 'Cycle opened: <name>')."""

    def close_cycle(self, project_code: str, gate_id: int) -> CycleRow:
        """Records the gate outcome (must be non-PLANNED — record_gate first)
        and closes the cycle. Delegates the I3 check to data/CycleRepo.close.
        Emits nothing extra (gate + cycle events come from data layer).
        Raises: GateMissing, CycleCloseError."""

    def record_gate(self, project_code: str, gate_id: int,
                    outcome: GateOutcome, actual_date=None) -> GateRow: ...

    def add_action(self, project_code, title, owner, description="",
                   priority=9, due_start=None, due_end=None,
                   cycle_id=None) -> ActionRow:
        """cycle_id defaults to the current open cycle. Emits via data."""

    def set_action_status(self, project_code: str, action_id: int,
                          new: ActionStatus) -> ActionRow:
        """Delegates to data (I4 lives there). Emits nothing extra."""

    def add_minutes(self, project_code, held_at, attendees, decisions,
                    agreed_actions, risks, minutes_text, cycle_id=None
                    ) -> MinutesRow:
        """Emits MEETING event via data layer. The agreed_actions text is
        free-form (PM types names); auto-creation of action rows from it is
        OUT of scope (frozen: PM adds actions explicitly — see scope)."""

    def list_for_project(self, project_code: str) -> ProjectSnapshot:
        """ONE query the UI needs: snapshot = project + current cycle +
        that actions (priority asc) + open gates + last 20 events (desc) +
        last 5 minutes + last 10 signals. ProjectRow/CycleRow/etc all from
        C2 rows. Raises UnknownProjectService."""
```

## C3.4 EngagementService

```python
class EngagementService:
    def record(self, project_code: str, kind: SignalKind, owner: str,
               action_id: int | None = None, note: str = "") -> SignalRow:
        """PM logs a defer/extension/late-start/reopen. Emits SIGNAL event
        via data layer. kind=REOPEN from here is the manual path (the
        automatic one fires inside set_action_status — both allowed)."""

    def mark_resolved(self, project_code: str, signal_id: int,
                      resolved: bool = True) -> SignalRow: ...

    def health_by_owner(self, project_code: str) -> list[OwnerHealth]:
        """OwnerHealth(owner: str, counts: dict[SignalKind, int],
                       total: int, open_total: int)
        Aggregates ALL signals for the project by owner. The report strip
        (C3.5) and the engagement view both call this — one definition,
        no duplicated aggregation logic (frozen rule)."""

    def list_for(self, project_code: str, kind=None, owner=None,
                 resolved=None) -> list[SignalRow]: ...
```

## C3.5 ReportService + the report payload (frozen content contract)

```python
class ReportService:
    def generate(self, project_code: str,
                 prepared_for: str | None = None) -> ReportRow:
        """1. payload = self._payload(project_code)   (from data snapshot
           + engagement health)
        2. html = renderer.to_html(payload)           (template is ui/report
           asset; renderer is C3.6)
        3. write reports/<code>/<date>_report.html (the SOURCE OF RECORD)
        4. pdf  = renderer.to_pdf(html_text)          (bytes)
        5. write reports/<code>/<date>_report.pdf
        6. report_history.add(..., snapshot_sha256=sha256(html_text))
        7. emit REPORT event (via data layer)
        Filename date = today UTC via core.now_utc().
        prepared_for default = project.sponsor (may be None -> page shows
        'Prepared for: —').
        Raises: PdfError (renderer failure — html file IS kept on disk,
        row NOT recorded, no event), UnknownProjectService."""

    def _payload(self, project_code: str) -> ReportPayload:
        """ReportPayload(project: ProjectRow, status: ProjectStatus,
                         target_date: date | None,
                         current_cycle: CycleRow | None,
                         priorities: list[ActionRow]   # open+in_progress,
                                                     # priority asc, top 5
                         red_flags: list[RedFlag],
                         escalations: list[SignalRow])
        RED FLAG rules (frozen, computed — not typed):
          RF-1 any open/in_progress action past due_end (late)
          RF-2 any gate with outcome FAILED or SKIPPED in current cycle
          RF-3 any signal unresolved with kind in {extension_request, reopen}
               and occurred within last 14 days
          RF-4 action reopen_count >= 2 (repeated reopen) -> flag the action
          RF-5 current cycle open > 30 days past its open cycle's first
               planned gate (stalled cycle) — compare to oldest open cycle
          Each RedFlag = (code, detail: str, ref: EventRef | None)
        ESCALATIONS (frozen): all unresolved signals of kind in
          {extension_request, reopen}, newest first, top 3.
          (Escalation = an engagement signal the PM marked as needing
          sponsor eyes; no separate table in v1 — frozen.)"""
```

Report page layout (frozen order — matches scope's "important information"):
header: project name · project target (target_date + objective line) ·
Status · Prepared for. Body: Current priorities (top 5 table). Red flags
(list, each with its code). Escalations (list). Engagement health strip
(bottom band, per owner: the four signal kinds with counts). Footer:
generated_at + 'PM Cockpit'. Exactly one page (A4) — overflow is a layout
BUG, asserted in the report test (D-02: asserted as byte/page check,
not by eyes).

## C3.6 Renderer (seam contract — the stub/real boundary for PDF)

```python
class Renderer:
    def to_html(self, payload: ReportPayload) -> str:
        """Renders from the static template ui/report/report.html.j2 (a
        Jinja2-free manual substitution template: {{field}} tokens
        replaced by str.format semantics — NO jinja2 dep in v1; tokens are
        a fixed list published in the template header comment). CSS inlined
        from ui/report/report.css (PRISM tokens: dark, one accent,
        tabular numerals). Deterministic: same payload => same html bytes."""
    def to_pdf(self, html_text: str) -> bytes:
        """WeasyPrint primary: HTML(string=html_text,
        base_url=<ui/report dir>).page_count must be 1 (asserted by
        ReportService before writing). Fallback (logged deviation D-02
        if WeasyPrint fails on target): Playwright headless — same html
        string, same page budget. Raises PdfError on any failure."""
```

Stub renderer (app/stubs): to_html returns a deterministic canned string
containing the payload's project code + a fixed token 'STUB-REPORT';
to_pdf returns minimal valid PDF bytes (a 1-page blank PDF built from a
byte constant in the stub) — enough for the smoke path and for wiring
tests that must NOT depend on the renderer install.

## C3.7 BackupService (stdlib only — shutil + hashlib + sqlite3 backup API)

```python
class BackupService:
    def create_backup(self, label: str | None = None,
                      dest_dir: str | None = None) -> BackupDescriptor:
        """dest_dir default: <workspace>/backups/<YYYY-MM-DD>_<label|full>/
        Steps: (1) sqlite3 backup API -> <dest>/app.db; (2) copy
        evidence/ + reports/ trees (shutil.copy2, preserving mtime);
        (3) write <dest>/MANIFEST.json: {'created_at', 'schema_version',
        'files': [{'rel_path','size','sha256'} ...]} over EVERY file
        copied (evidence + reports + app.db); (4) update
        meta.last_backup_at. BackupDescriptor(count_files, dest, ok=True).
        Never touches open-file exclusions: the app is single-process and
        this runs from the same process — SQLite's backup API handles the
        live db safely; if the db handle is closed, fall back to shutil copy
        (frozen: either path is acceptable, MANIFEST is required on both)."""

    def restore(self, backup_dir: str) -> RestoreReport:
        """Restores into the CURRENT workspace root: copy app.db over
        (close live handle first, via DataKit.close() injected for this
        op — composition root wires it), restore evidence/ + reports/,
        then IntegrityService.verify() over the result.
        RestoreReport(ok, verified_ok, missing_count, mismatch_count,
                      orphan_count). Raises MissingFileError if the backup
        dir lacks MANIFEST.json. NEVER deletes workspace content that the
        backup does not contain (files are overwritten, orphans remain —
        frozen: restore = merge-over, documented)."""
```

## C3.8 HandoverService

```python
class HandoverService:
    def export(self, project_code: str, dest_dir: str) -> str:
        """Builds <dest_dir>/<code>_handover.zip containing:
           db_slice.json      -- that project's rows: projects, events,
                                cycles, gates, actions, evidence, minutes,
                                signals, report_history (all as dicts,
                                created_at-first key order)
           story.md           -- ALL timeline events of the project,
                                occurred_at asc, one bullet each:
                                '[YYYY-MM-DD] (kind) title — summary'
                                plus sections: open actions, unresolved
                                signals, gate history
           evidence/ ...      -- the project's evidence folder, relative
                                paths preserved, each file's sha256 listed
                                in the zip's story.md appendix (table)
           reports/ ...       -- generated reports
           manifest.json      -- export meta: exported_at, schema_version,
                                file count, manifest of all entries + sha256
        Returns the zip path. Raises UnknownProjectService.
        (This is the 'Documentation and handover' phase artifact — scope
        flow: Project delivery -> Documentation and handover -> Finished.)"""
```

## C3.9 Service stubs (app/stubs/services.py)
Implement every ServiceKit method with deterministic canned behavior:
  - Project listing reflects the data stub (P001/P002); create_project
    returns P003 canned; attach() returns a canned row (no file copied);
    record/close/add_action return canned rows + no side effects;
    generate() returns a canned ReportRow (html_rel_path
    reports/P001/2026-08-01_report.html, pdf the same stem, prepared_for
    'Sponsor A', snapshot_sha256 'stub'*8) and uses the stub Renderer;
    backup returns a canned descriptor (no disk write); export returns
    '<dest>/P001_handover.zip' string without writing.
  - Every stub raise-path mirrors the real contract's error types (tests
    exercise one: list_for('P999') raises UnknownProjectService).
Determinism rule (frozen): stubs never call time.time() — fixed timestamps.
