# TODO — build-state log (update after every card closes)

Current gate: **Phase 1 pending** — P-00 (green skeleton with stubs) must
pass `make gate` (ruff + mypy + pytest) before any real logic is written.

## Immediate

- [ ] P-00 green skeleton: package layout `app/ core/ data/ services/ api/ ui/`
      + `app/stubs/`, Makefile (`gate` target), 100% stub suite, smoke e2e
      (`GET /api/health` 200, canned project visible), all `cfg.wired.*` false
- [ ] Environment install on the build machine:
      `fastapi uvicorn pydantic pywebview weasyprint pytest httpx ruff mypy`
- [ ] M0 verification (due 2026-08-20): pywebview on the target Windows
      laptop (fallback: Edge), PDF renderer choice, PRISM_UI_Protocol in hand
      or written waiver

## Next (card order, MOSAIC)

- [ ] P-01..P-06 — core (enums, values, paths, errors, time, hash) + data
      (migration, DataKit, repositories, invariants I1–I4, FTS5 search,
      integrity)
- [ ] S-01 — wire data (stub repositories → real repositories), contract suite
      green
- [ ] P-07..P-15 — services (evidence, flow, engagement, report, backup,
      handover) + api (routes, views, error envelope, loopback)
- [ ] S-02 — wire renderer (stub → real PDF renderer)
- [ ] S-03 — wire services (stub → real services)
- [ ] P-16..P-25 — ui (shell, project views, timeline, action board, signals,
      report view) + handover/demo data
- [ ] S-04 — final e2e through the real system, full regression, tag v0.1
- [ ] P-28 story-acceptance (determinism), P-29 clone-build + handover doc,
      tag v1.0.0

## Standing rules

- Never build on red: a failing gate stops all forward work until green.
- Contracts (C1–C4) are frozen — changes only via a CC card.
- Stubs never leak past the composition root into a wired path.
- Relative paths only in app.db (glue rule).
- Visible increment every build day; demo at each milestone gate (M1 AC1,
  M2 AC1–AC5, M3 handover).
