# BUILD_STATE — PM Cockpit bundle (running log, one line per gate)

Phase 0 (Blueprint): BLUEPRINT-OK — 00 + 4 contracts + README + 30 cards
  (P-00..P-29) produced 2026-08-19 v1.0.
Phase 1 (Phase 1 gate): PENDING — P-00 must pass `make gate` (green
  skeleton, stub suite, smoke e2e).
Phase 2 (card gates): PENDING — P-01..P-26 each must pass the full
  gate before the next card starts. Order below.
Phase 3 (seam): PENDING — P-27 all-real kit must pass the SAME suite
  the stubs passed. A seam failure = a contract defect → CC card,
  never a test edit (MOSAIC §4).
Phase 4 (integration + handover): PENDING — P-28 story-acceptance
  (incl. determinism) → P-29 (clone-build + handover doc) → tag v1.0.0.

Risks tracked (M0 verification 2026-08-20):
  R1 pywebview on target Windows laptop — fallback: Edge kiosk
     (app/window.py adapter abstracts it; the seam does not care).
  R2 PDF renderer (weasyprint vs headless Edge print-to-PDF) —
     chosen in P-17 at M0; contract C3.6 names TO, not HOW.
  R3 PRISM_UI_Protocol file from PM (A6, due 2026-08-20) —
     fallback: built-in professional set, deviation logged here
     (scope §12).
Dependencies: stdlib + fastapi + uvicorn + pywebview(or Edge) +
  ONE pdf renderer (R2) + pytest/httpx/mypy/ruff (tooling) +
  playwright (tests, dev-only). No ORM, no Docker, no server role.

Build order (MOSAIC Phase 2 sequence):
  P-01 P-02 P-03 P-04 | P-05 P-06 P-07 P-08 P-09 |
  P-10 P-11 P-12 P-13 P-14 P-15 | P-16 P-17 |
  P-18 P-19 P-20 | P-21 P-22 P-23 P-24 P-25 | P-26 |
  P-27 (SEAM) | P-28 (STORY) | P-29 (HANDOVER → v1.0.0)

Completion line (written by P-29, asserted by test):
  BUNDLE COMPLETE — 29 cards, seam green, clone green, determinism green
