# CONTRACT C4 — api (FROZEN after Phase 1 — changes only via a CC card)

api/ = a thin HTTP layer over ServiceKit (read paths also use kit.data
directly — the ONLY place outside services that may touch DataKit, per the
C3 rule). Binds 127.0.0.1 ONLY. JSON everywhere. No auth (single-user,
local; frozen — auth is out of scope by design, not by omission).

## C4.0 App assembly

```python
def create_app(kit: ServiceKit) -> "FastAPI":
    """The ONLY construction path. Stores kit in app.state. No module-
    level database. No global singletons."""

def main(workspace_root: str | None = None, port: int | None = None,
         open_window: bool = True) -> None:
    """reads config.json (workspace + port), builds the kit via the
    composition root (app/root.py), starts uvicorn on 127.0.0.1, then
    opens the pywebview window (if available and open_window).
    Fallback: if pywebview import fails, print the URL +
    'Open in Edge' and continue (D-02 / risk R1 in ARCHITECTURE.md)."""
```

config.json (workspace root):  {"workspace": "D:/PM-Cockpit"...
use forward slashes in the file even on Windows (frozen), "port": 8765,
"theme": "dark"}. First run (no config.json): write defaults,
workspace = <userprofile>/Documents/PM-Cockpit.

## C4.1 Routes (exact paths, methods, and JSON shapes)

### Health
  GET /api/health -> {"ok": true, "schema_version": "1", "projects": <int>}
      # (projects count = kit.data.projects.list() len — the stub returns 2;
      # the api MUST NOT import DataKit itself: it calls kit.data — kit is
      # the boundary, so this is a service call in shape, C3-compliant.)
  GET /            -> 200 served index.html (ui assets mounted at /static)

### Projects
  GET  /api/projects
       -> {"projects": [ProjectView ...]}   # list, any status
  POST /api/projects
       body {"name": str, "sponsor": str|null, "target_date": "YYYY-MM-DD"|null,
             "objective": str, "charter_text": str, "constraints_text": str}
       -> 201 {"project": ProjectView}
       # errors: 422 -> {"error":{"code":"validation","message":...}};
       #          400 -> {"error":{"code":"...","message":...}} for
       #          CoreError/ServiceError/DataError — the error envelope
       #          (C4.2) maps EVERY CoreError subclass to
       #          {"error":{"code": err.code, "message": str(err)}}.
  GET  /api/projects/{code}
       -> {"project": ProjectView, "snapshot": SnapshotView}
       # snapshot = kit.flow.list_for_project(code) rendered as SnapshotView
  POST /api/projects/{code}/set_status
       body {"status": "active"|"in_review"|"delivered"|"closed"}
       -> {"project": ProjectView}
  POST /api/projects/{code}/set_sponsor
       body {"sponsor": str}   -> {"project": ProjectView}

### Evidence
  POST /api/projects/{code}/evidence
       multipart/form-data: file (binary), source_type (one of core enum
       strings, default "other"), note (optional text)
       -> 201 {"evidence": EvidenceView}
  GET  /api/projects/{code}/evidence
       -> {"evidence": [EvidenceView ...]}
  DELETE not in v1 (frozen: evidence is never deleted by the app — the
       PM removes files manually if ever needed; a removed file surfaces
       as a missing-file flag in integrity, which is the designed behavior
       per I2. This is a deliberate non-feature, logged.)

### Actions
  POST /api/projects/{code}/actions
       body {"title", "owner", "description", "priority" (1-9),
             "due_start"|"due_end" (dates, optional), "cycle_id" optional}
       -> 201 {"action": ActionView}
  PATCH /api/projects/{code}/actions/{id}
       body {"status": ActionStatus string}     (only field in v1 — frozen;
       adding fields later is a CC card)
       -> {"action": ActionView}
       # illegal transition -> 400 envelope code "illegal_transition"
  GET  /api/projects/{code}/actions
       -> {"actions": [ActionView ...]}         # ordered priority asc,
                                                # then due_end asc, then id

### Cycles & gates
  POST   /api/projects/{code}/cycles
         body {"name"} -> 201 {"cycle": CycleView}
         # 400 code "cycle_open" if one is already open
  POST   /api/projects/{code}/gates
         body {"name", "planned_date"|null, "exit_criteria", "notes"}
         -> 201 {"gate": GateView}
  POST   /api/projects/{code}/gates/{id}/outcome
         body {"outcome": "passed"|"conditionally_passed"|"failed"|"skipped",
               "actual_date"|null}
         -> {"gate": GateView}
  POST   /api/projects/{code}/cycles/{id}/close
         body {"gate_id": int}
         -> {"cycle": CycleView}
         # 400 code "gate_missing" when the gate has no recorded outcome
  GET    /api/projects/{code}/gates -> {"gates": [GateView ...]}

### Minutes
  POST /api/projects/{code}/minutes
       body {"held_at", "attendees", "decisions", "agreed_actions",
             "risks", "minutes_text", "cycle_id"|null}
       -> 201 {"minutes": MinutesView}
  GET  /api/projects/{code}/minutes
       held_at desc, top 20 by default; ?limit=N honored (max 100).

### Engagement
  POST /api/projects/{code}/signals
       body {"kind": "defer"|"extension_request"|"late_start"|"reopen",
             "owner": str, "action_id"|null, "note": str}
       -> 201 {"signal": SignalView}
  PATCH /api/projects/{code}/signals/{id}/resolved
       body {"resolved": true|false} -> {"signal": SignalView}
  GET  /api/projects/{code}/signals
       query params: kind, owner, resolved (filter)  -> {"signals":[...]}
  GET  /api/projects/{code}/engagement/health
       -> {"health": [OwnerHealthView ...]}
       # OwnerHealthView = {"owner","counts":{kind:int},"total","open_total"}

### Report
  POST /api/projects/{code}/report
       body {"prepared_for": str|null}     # null => project sponsor => '—'
       -> 201 {"report": ReportView, "open_intent": "explorer"}
       # open_intent is a HINT string for the ui (it may shell-execute the
       # html file); the api never launches anything itself (frozen).
  GET  /api/projects/{code}/reports
       -> {"reports": [ReportView ...]}  generated_at desc, top 20

### Search (the single search box)
  GET /api/search?terms=<text>&project=<code>&limit=50
       -> {"hits": [HitView ...]}   # HitView {"table","row_id","snippet"}
       # table in {"minutes","evidence","events"} (frozen set)
       # 400 code "fts_unavailable" only if the FTS table is missing.

### Backup / restore / handover
  POST /api/backup
       body {"label": str|null, "dest_dir": str|null}
       -> 201 {"backup": {"dest": str, "files": int, "ok": true}}
  POST /api/restore
       body {"backup_dir": str}
       -> {"restore": {"ok": bool, "verified_ok": bool, "missing": int,
                       "mismatched": int, "orphans": int}}
  POST /api/projects/{code}/handover
       body {"dest_dir": str|null}   # null => desktop default
       -> 201 {"handover": {"zip": str, "ok": true}}

### Integrity
  GET /api/integrity
       -> {"integrity": IntegrityView}
       # IntegrityView {"ok": bool, "missing": int, "mismatched": int,
       # "orphans": int, "missing_list": [rel_path ...],
       # "orphan_list": [rel_path ...] top 50 each}

## C4.2 Error envelope (single mapping, frozen)

```json
{"error": {"code": "<err.code>", "message": "<str(err)>"}}
```
- 400 for CoreError/ServiceError/DataError (business rules).
- 404 for: unknown route (envelope, not HTML), unknown project code
  (UnknownProjectService/UnknownProjectData -> code "unknown_project" is
  mapped to 404, not 400 — frozen), unknown action/cycle/gate/signal id
  (code "not_found" -> 404).
- 409 for EvidenceConflict (code "evidence_conflict", 409).
- 422 for FastAPI body validation failures (code "validation").
- 500 for anything else (code "internal", message = exception str).
A single global exception handler maps CoreError -> its HTTP class per the
table above; every route's happy path returns 2xx with the View shape named.

View shapes (api/views.py <= 300 lines — if it grows, split into
api/views_projects.py / api/views_actions.py, both <= 300, R10):
  ProjectView  {code,name,sponsor,target_date,status,objective,created_at}
  SnapshotView {project, current_cycle, actions[], gates[], events[],
                minutes[], signals[]}     # all sub-Views, events top 20
  ActionView   {id,project_code,cycle_id,title,owner,description,priority,
                due_start,due_end,started_at,closed_at,status,reopen_count}
  EvidenceView {id,project_code,rel_path,sha256,size,mime,source_type,
                note,attached_at}
  CycleView {id,project_code,name,opened_at,closed_at,gate_id}
  GateView  {id,project_code,name,planned_date,actual_date,outcome,
             exit_criteria,notes}
  MinutesView {id,project_code,cycle_id,held_at,attendees,decisions,
               agreed_actions,risks,minutes_text}
  SignalView  {id,project_code,owner,kind,action_id,occurred_at,note,
               resolved,resolved_at}
  ReportView  {id,project_code,generated_at,pdf_rel_path,html_rel_path,
               prepared_for,snapshot_sha256}
  Date fields as "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SSZ" strings (frozen).

## C4.3 UI intents (the api's one bridge to OS, frozen)
  GET /api/ui/open?rel_path=<evidence or report html/pdf path>
       -> {"opened": true, "path": "<abs>"}  on Windows: os.startfile (the
       ONLY shell-execute in the app); on any other OS (dev/testing): just
       resolve and return the path without executing. 400 PathEscape for
       anything not under the workspace. This is how the PM double-clicks
       an evidence file or opens the just-generated report — one intent,
       one route, used by the whole ui.

## C4.4 Loopback hardening (architecture constraint, frozen)
  uvicorn run_config: host="127.0.0.1" HARDCODED in api/server.py, port
  from config (default 8765). A test asserts the running server's bind
  address is loopback (connects 127.0.0.1:port OK) and that the config
  cannot override host (config.json "host" key is IGNORED — documented in
  config schema comment). No CORS needed (same origin); do NOT add a CORS
  middleware (frozen: nothing cross-origin is served or consumed).

## C4.5 api module layout (R10 sizes)
  api/__init__.py    re-export create_app, main
  api/app.py         create_app + exception handlers          <=300
  api/server.py      uvicorn entry + loopback guard            <=60
  api/routes_projects.py   projects + projects sub-noun routes <=300
  api/routes_actions.py    actions + cycles + gates            <=300
  api/routes_comms.py      minutes + signals + engagement      <=300
  api/routes_outputs.py    report + search + backup + restore
                           + handover + integrity + ui open    <=300
  api/views.py         View dataclasses + from_row converters  <=300
