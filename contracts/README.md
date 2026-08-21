# PM Cockpit — MOSAIC Build Bundle v1.0 (2026-08-19)

This bundle is the complete Phase 0 (Blueprint) + Phase 2 (Card set) deliverable
for PM Cockpit, built under the MOSAIC Build Protocol. It is self-contained:
the build agent needs nothing outside this folder plus the stack it installs.

Upstream documents (provenance only — the bundle contains everything needed
to build):
  - SCOPE.md          — L2 scope v0.2 (what and why, acceptance, deadlines)
  - ARCHITECTURE.md   — design rationale v0.1 (stack choices, storage glue rule)

## 0. What this bundle is

- 00-ARCHITECTURE.md   — one-page blueprint: purpose, module map, DAG, per-module acceptance criteria
- 01..04-CONTRACTS-*.md — FROZEN boundary contracts (core, data, services, api).
                          This is the only vocabulary modules may use to talk to
                          each other. Changing one after Phase 1 requires a CC
                          (contract change) card — never an inline edit.
- 05-BUILD_STATE.md    — external memory. Read it first, update it last, every session.
- cards/               — P-xx.md portion cards and S-0x seam cards, in build order.

## 1. Non-negotiable rules (MOSAIC prime rules, as applied here)

R1  No task larger than one context window. Pack + expected output must fit.
R2  Contracts before code. They are frozen in this bundle (Phase 0 complete).
R3  Skeleton before flesh. P-00 assembles the whole system shape with stubs;
    the architecture is proven before any real logic exists.
R4  One portion at a time. Each card independently buildable and verifiable.
R5  External memory is mandatory. BUILD_STATE.md and these cards ARE the memory.
R6  Never build on red. A failing gate stops all forward work until green.
R7  Edit, don't regenerate. Targeted diffs. Whole-file regeneration causes drift.
R8  Wire one seam per session. Wiring is its own card (S-01..S-04), its own commit.
R9  Contracts frozen after Phase 1. Change only via a CC-xx card.
R10 Size caps: Python module ≤ 300 lines · function ≤ 40 lines · a portion
    touches ≤ 2 source files + their tests.

## 2. Session loop (every OpenHands session, exactly this order)

1. Read 05-BUILD_STATE.md. Take the next card (or resume the in-progress one).
2. Load ONLY the card's Context Pack. Nothing else enters the prompt.
3. Write the card's unit tests first (from the acceptance bullets), then implement.
4. Self-review against "Done when".
5. Run `make gate`. Red => fix now (max 3 attempts, then STOP with BLOCKED:).
6. Green => update 05-BUILD_STATE.md, commit with the portion ID, stop.

Outputs that mean the work cannot proceed (say them verbatim, do not improvise):
  SPLIT:   <why it does not fit> + proposed sub-portions
  BLOCKED: <failing output verbatim> + what was tried + options

## 3. Wiring ("the wires connect at the end")

User directive for this build: bottom-up, all structural seams wired at the end
in dependency order. Each seam card flips exactly one cfg.wired flag, runs the
contract suite (real impl appended to IMPLS) + full regression + e2e, and
commits. Red => flip the flag back (instant rollback) and fix as a portion.

Seams, in order:
  S-01 data        (stub repositories  -> real repositories)
  S-02 renderer    (stub renderer     -> real PDF renderer)
  S-03 services    (stub services     -> real services)
  S-04 final       (e2e through the real system, full regression, tag v0.1)

Contract suites are parametrized over implementations: the stub passes the
suite in P-00, and every real implementation must pass the SAME suite before
its seam flips. That property — not hope — is what makes the late wiring safe.

## 4. Environment and gates

Target: Windows, Python 3.12+, local single-user app (scope: no server, no
internet at runtime). Build-time pip install is normal development activity.

  pip install fastapi uvicorn pydantic pywebview weasyprint
              pytest httpx ruff mypy

Gate command (must be green before any portion closes):

  make gate  ==  ruff format --check . && ruff check . \
                 && mypy app contracts && pytest -q

P-00 writes the Makefile. Until P-00, run the four commands by hand.

## 5. Phase gates and commits

  P-00 gate (exit Phase 1): smoke e2e green with 100% stubs · all contract
     tests green · cfg.wired.* all false · commit tagged skeleton-green.
  Every part card: per-card Done-when bullets · commit "P-xx green".
  S-04 gate (exit build): smoke + full regression green on the REAL system ·
     commit tagged v0.1.

Commit convention: <CARD-ID> <short verb> (e.g. "P-07 attach evidence service",
"S-01 wire data, real repos green").

## 6. Logged deviations from MOSAIC

D-01 Tracer bullet (§9.5) deferred: MOSAIC's default order puts a thin real
     end-to-end path early. User directive for this project is explicit
     bottom-up build with all wiring at the end; the real e2e lands at S-04.
     Risk mitigation: every real module passes the identical contract suite
     the stub passed (MOSAIC §4.3), and seams flip one at a time with instant
     rollback — so the deferred integration cannot hide a structural error.
     Revisit condition: if S-04 fails on a cross-module mismatch, the fix is
     a portion, logged here.

D-02 UI testing: no browser-automation dependency in the build gate (install
     risk on the target machine, 12-day clock). UI cards verify by served-asset
     checks + DOM presence assertions via httpx; visual acceptance is a manual
     UAT step in the project plan (M2 in SCOPE.md), not a build-gate claim.

## 7. Anti-patterns that will fail review on this project

  1. Building a card from files outside its Context Pack.
  2. Editing a contract inline. (CC card, always.)
  3. A portion that edits another module to "make it fit".
  4. Canned/stub data leaking past the composition root into a wired path.
  5. Storing absolute paths in app.db (glue rule: relative paths only).
  6. Proceeding to the next card while any gate is red.
