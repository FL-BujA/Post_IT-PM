# ARCHITECTURE — PM Cockpit (one-page blueprint, per MOSAIC Phase 0)

Purpose: A local, single-user Windows desktop application for a project
manager. It runs one project's management loop — charter -> action plan ->
priorities -> execution -> verification gates -> next cycle -> delivery ->
handover — with a parallel lane of evidence capture, meeting minutes and
one-page stakeholder reporting. Multi-project. No server, no internet at
runtime. All state = one SQLite file + per-project evidence folders, backing
up as a folder copy.

## Module map (DAG — no cycles, ever)

| Module              | Single responsibility (one sentence)                     | Depends on |
|---------------------|----------------------------------------------------------|------------|
| core/               | Pure domain types: enums, ids, slugs, hashing, paths     | stdlib only |
| data/               | SQLite access: db lifecycle, migrations, repositories, invariant enforcement | core |
| services/           | Use cases: evidence, flow, engagement, report, backup, handover, render | core, data |
| api/                | HTTP layer: create_app, route groups, error envelope (127.0.0.1 only) | core, services |
| ui/                 | Static HTML/CSS/JS shell (PRISM tokens) + view assets    | (serves via api) |
| app/                | Composition root + launcher: the ONLY place stub->real is chosen | all |
| app/stubs/          | One stub per boundary, kept forever as test doubles      | contracts |

Dependency rule: arrows point only downward. ui/ is static files served by
api/; it imports nothing. app/ imports everything and is imported by nothing.

```
            ui (static assets, served)
              ^
core  ->  data  ->  services  ->  api  <-  app (composition root)
 ^                                                ^
 +---------------- stubs (implement contracts) --+
```

## Acceptance criteria per module (their tests encode these)

core
- Enum values serialize to lowercase strings and back without loss.
- slugify rejects/normalizes policy violations; raises InvalidSlug on empty.
- normalize_relpath passes 'evidence/P001/x.pdf', rejects 'a/../b' and '/abs'
  (PathEscape). Evidence filename format is exactly YYYY-MM-DD_slug.ext.
- sha256_file matches hashlib on the same bytes; works for 0-byte and 50 MB.

data
- migrate() is idempotent; schema_version lands in meta on first open.
- tx() commits on return, rolls back on exception (verified by test).
- set_status done->open increments reopen_count and emits BOTH the
  action_status timeline event and a SignalKind.reopen row (I4).
- close_cycle with no gate row or a gate whose outcome is NULL raises
  IntegrityViolation (I3).
- verify() flags a row whose file is missing (I2) and reports a file with no
  row as orphan; neither condition deletes anything.
- search() returns hits from minutes_text, evidence.note and event summaries
  with table/id/snippet; respects project_code filter and limit.

services
- attach() copies the file into evidence/<code>/, persists the glue row
  (rel_path, sha256, size, mime, source_type), emits the evidence event;
  re-attaching the same rel_path is rejected (evidence conflict).
- close_cycle passes a recorded gate outcome through to data; a missing/
  un-outcomed gate raises CycleCloseError with the gate id in the message.
- health_by_owner() aggregates the four signal kinds per owner and matches
  the stored signals exactly (property test with random signals).
- generate() produces html_rel_path + pdf_rel_path under reports/<code>/,
  one PDF page (asserted), records report_history with prepared_for and
  snapshot_sha256, emits the report event.
- createBackup -> restore (to a pristine copy) => verify() ok=True and all
  evidence hashes match (restore test).
- export() produces a zip containing: db slice json, evidence folder, reports
  folder, story.md; the story lists every timeline event in order.

api
- create_app assembles from the injected ServiceKit only (no module-level DB).
- Every 4xx/5xx returns the error envelope {"error":{code,message}}.
- Loopback-only: host is 127.0.0.1 regardless of config tampering tests assert.
- Each endpoint documented in 04-CONTRACTS-api.md returns the frozen shape;
  unknown route => 404 envelope (not 404 HTML).
- Multipart evidence upload round-trips a file whose content hash equals the
  stored sha256.

app (composition root + launcher)
- build_app(wired) returns the same app object type for all flag combos;
  wired flags are the ONLY stub/real selector.
- With all flags false: /api/health is 200 and a canned project is visible
  (smoke). With all true: real data persists across an app restart.

ui
- index.html loads with the PRISM token variables defined in prism.css and
  no console-referenced 404 (checked by served-asset assertions).
- Every view id referenced by app.js exists in the served HTML (D-02).

## Build order (authoritative copy: 05-BUILD_STATE.md)

P-00 skeleton (Phase 1) -> P-01..P-06 core+data -> S-01 wire data
-> P-07..P-13 services -> S-02 wire renderer, S-03 wire services
-> P-14..P-17 api -> P-18..P-22 ui -> S-04 final e2e + regression (v0.1)

## Frozen context (do not re-litigate during build)

- Stack per ARCHITECTURE.md v0.1: Python 3.12, FastAPI single process on
  127.0.0.1, pywebview window (Edge fallback), SQLite, stdlib backup,
  WeasyPrint (Playwright fallback) for PDF — the report HTML is the source
  of record for both.
- Glue rule: DB stores references+hashes, disk stores bytes, relative paths
  only (anti-pattern #5 in README).
- No ORM, no Docker, no Electron, no webmail ingestion, no Gantt in v1
  (recorded rejections in ARCHITECTURE.md §9 of the project folder).
