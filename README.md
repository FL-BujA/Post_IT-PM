# PM Cockpit (Post_IT-PM)

A local, single-user Windows desktop application for a project manager. It runs
one project's management loop — charter → action plan → priorities → execution
→ verification gates → next cycle → delivery → handover — with a parallel lane
of evidence capture, meeting minutes, and one-page stakeholder reporting.
Multi-project. No server, no internet at runtime.

All state lives in one workspace folder: a single SQLite file (`app.db`) plus
per-project evidence and report folders, backed up as a folder copy with
checksum verification.

## Stack (frozen)

| Layer    | Choice                                                    |
|----------|-----------------------------------------------------------|
| Language | Python 3.12+                                              |
| Backend  | FastAPI, single process, bound to 127.0.0.1 only         |
| Database | SQLite (one `app.db`, WAL mode)                           |
| UI       | Local HTML/CSS/JS served from the app (PRISM design tokens) |
| Window   | pywebview native window (fallback: local Edge)           |
| PDF      | WeasyPrint from the same PRISM-styled HTML (fallback: Playwright headless) |

## Repository layout

- `SCOPE.md` — v1 scope, acceptance criteria AC1–AC5, milestones M0–M3
- `CODEX_PROMPT.md` — build instructions for the build agent
- `TODO.md` — current build-state log (card progress, gates)
- `CHANGELOG.md` — meaningful changes, newest first
- Application source (planned): `app/` (composition root), `core/`, `data/`,
  `services/`, `api/`, `ui/`, `app/stubs/` — built card by card per the
  contracts (C1–C4) in the MOSAIC blueprint.

## Building

```
pip install fastapi uvicorn pydantic pywebview weasyprint pytest httpx ruff mypy
```

Gate (must be green before any build portion closes):

```
make gate   # ruff format --check . && ruff check . && mypy app contracts && pytest -q
```

## Non-negotiable rules

- Contracts before code; contracts frozen — changes only via a CC card.
- Skeleton before flesh; one portion at a time; never build on red.
- Glue rule: the DB stores relative paths + SHA-256 + metadata; the file on
  disk is the source of truth for content. Absolute paths in the DB are banned.
- No ORM, no Docker, no Electron, no webmail ingestion, no Gantt in v1.
- Loopback only: host 127.0.0.1 is hardcoded; nothing ever phones home.
