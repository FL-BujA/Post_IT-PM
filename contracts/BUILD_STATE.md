# BUILD_STATE — Post_IT-PM (running log)

Updated: 2026-08-22. This file is the memory (MOSAIC R5). If it disagrees
with the repository, the repository is right and this file is stale — say so
rather than working from it.

## Phase

Phase 0 (Blueprint): DONE — 00-ARCHITECTURE + 4 contracts + README, 2026-08-19.
Phase 1 (skeleton):  DONE — P-00 gate green.
Phase 2 (cards):     IN PROGRESS — core and data layers closed, services layer
                     in progress. Next card: P-12.
Phase 3 (seam):      PENDING — P-27.
Phase 4 (handover):  PENDING — P-28 then P-29 → tag v1.0.0.

Last green commit: 802b70a (P-11). `make gate` green, 257 tests.

## Cards done

    P-00 .. P-08   core layer, then data repositories        (see note 1)
    P-09a          minutes + signals repositories             0091ebc
    P-09b          report history + FTS5 search               e396217  (note 2)
    P-09c          integrity (I2) + DataKit closure           99a3a90
    P-09d          backfill SignalRow/MinutesRow/ReportRow    28a107a
    P-09e          Minutes+ReportHistory return typed rows    f1523fb
    P-05a          engagement_signals DDL → migrate.py        9284446  (note 3)
    P-05b          meeting_minutes + report_history DDL       f5c450a  (note 3)
    P-10a-i        ServiceKit skeleton, placeholder slots     fced34b
    P-10a-ii       project lifecycle service                  461d8b7
    P-10b          phase lifecycle, I3 service-side guard     145588c
    P-11           actions, priorities, engagement (I4)       802b70a

## Cards remaining

    P-12 P-13 P-14 P-15 | P-16 P-17 | P-18 P-19 P-20 |
    P-21a P-21b P-22 P-23 P-24 P-25a P-25b | P-26a P-26b |
    P-27 (SEAM) | P-28 (STORY) | P-29 (HANDOVER → v1.0.0)

P-16, P-18 and P-21a each open a directory that does not exist yet. Expect to
split each into a seed card plus a build card, as P-10a required — see note 5.

## Deviations logged

D1 — REGISTER convention (2026-08-21). R10 allows 2 source files per portion.
     Single-line registration edits (a slot assignment, a router include, a
     view mount, a pinned dependency) are labelled REGISTER on the card and do
     not count toward the two, provided they are line edits only and under
     five changed lines. 22 of 27 rewritten cards need exactly one.

D2 — CC-01, core public-surface rule (2026-08-21). 01-CONTRACTS-core.md:110
     was amended from "<= 7 per module" to "<= 7 public callables and types;
     an exception hierarchy counts as one; module-level constants and compiled
     patterns excluded". OPEN QUESTION: this amendment was made on a misreading
     — MOSAIC R10 does state "public API of a module <= 7 symbols", so
     core.errors at 14 names is a genuine violation under the literal rule.
     The amendment may still be the right call, but it should be re-decided
     deliberately rather than left as a correction of a mislabel.

D3 — card splits (2026-08-21/22). P-09 (5 source files), P-10 (3), P-21 (3),
     P-25 (4) and P-26 (3) exceeded R10 and were split with letter suffixes.
     P-10a was split again into P-10a-i/ii after four failed sessions. Every
     card that named more than two source files failed to produce output;
     every card naming two or fewer built on the first or second attempt.

## Defects found and fixed

F1 — signature sheet truncated (2026-08-22). core.sig.txt was generated with
     `grep "def \|class "`, which keeps only the first physical line and
     discarded the parameter list of every wrapped signature. Cards that had
     to call into another layer were given a sheet naming functions and
     nothing else. Fixed by tools/sigsheet.py (AST-based, with a self-test).

F2 — signature sheet incomplete (2026-08-22). The first AST version emitted
     class names but not dataclass fields, so no card could learn a row's
     shape without opening the source. Same fix; the self-test now asserts
     fields, enum members and wrapped signatures all survive.

F3 — schema outside the migration (2026-08-22). C2.0 defines fourteen tables;
     data/migrate.py created eleven. meeting_minutes, engagement_signals and
     report_history were created ad hoc by the repositories that needed them,
     engagement_signals by data/actions.py which does not own it. A comment in
     that file claimed "the frozen C2.4 DDL does not create it" — a misreading;
     C2.4 describes the migration in prose and C2.0 is the table list. Fixed
     by P-05a and P-05b. A test now asserts the sqlite_master table count
     matches C2.0, so this cannot recur silently.

F4 — repositories violated their contract's return types (2026-08-22).
     MinutesRepo, SignalRepo and ReportHistoryRepo returned list[tuple] where
     C2.2 specifies list[MinutesRow], list[SignalRow], list[ReportRow]. The
     three row classes named in C2.0 were never created. All three cards went
     green because their Done-when bullets asserted behaviour and never types.
     Fixed by P-09d and P-09e.

## Standing checks

- `make gate` runs the sigsheet self-test, the staleness check, and pytest.
  A card that changes a public surface must regenerate core.sig.txt; the gate
  catches it if the card forgets.
- pytest is not installed in a fresh sandbox. `pip install -q pytest` first.
  This should become a dev dependency in pyproject.toml.
- Commit descriptions come from the card's `Commit:` line, not from the
  previous message. Five commits carry a description copied forward by hand
  (e396217, 9284446, f5c450a and the P-01..P-07 range) — the card prefix is
  correct in each, the description is not.

## Risks

R1 — pywebview on the target Windows laptop. Fallback: Edge kiosk. The
     app/window.py adapter abstracts it; the seam does not care. Decided at
     P-26a.
R2 — PDF renderer (weasyprint vs headless Edge print-to-PDF). Chosen in P-17.
     Contract C3.6 names WHAT, not HOW.
R3 — PRISM_UI_Protocol from PM. Fallback: built-in professional token set,
     deviation to be logged here (scope §12). Decided at P-21a.

## Dependencies

stdlib + fastapi + uvicorn + pywebview (or Edge) + ONE pdf renderer (R2) +
pytest / httpx / mypy / ruff (tooling) + playwright (tests, dev only).
No ORM, no Docker, no server role. P-29 asserts the count is unchanged from
P-17 onward.

## Notes

1. P-01..P-08 commits carry a recycled description ("paths and value objects")
   from P-02 onward. The card prefix identifies them; the description does not.
   Read the diff to know what a commit in that range did.
2. e396217 is labelled "P-09c" but contains P-09b's work. 99a3a90 is the real
   P-09c. History not rewritten.
3. P-05a and P-05b are backfills against an already-passed P-05, not new
   portions in the original sequence. They carry P-05's number because they
   correct P-05's output.
4. The signature sheet is regenerated by `python3 tools/sigsheet.py` and
   verified by `--check` in the gate. It covers core/, data/ and services/;
   add a layer to LAYERS in that file when one is created.
5. Cards opening a new directory need a seed card first: package plus typed
   placeholders, no logic, no outbound calls, and a Context Pack naming one
   contract section and nothing else. P-10a-i is the worked example.

## Completion line (written by P-29, asserted by test)

    BUNDLE COMPLETE — <n> cards, seam green, clone green, determinism green

The card count is no longer 29. Set it from the actual card list when P-29
is written.
