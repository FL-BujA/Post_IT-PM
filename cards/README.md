# Rewritten cards — P-09 through P-29

21 original cards became 27. Nothing was dropped: every "Done when" bullet
from the originals survives, redistributed where a card was split.

## Why the rewrite

P-09 and P-10 each stalled across multiple sessions producing zero output.
Both exceeded MOSAIC R10:

> R10 Size caps: module ≤ 300 lines · function ≤ 40 lines · public API of a
> module ≤ 7 symbols · a portion touches ≤ 2 source files + their tests.

P-09 named 5 source files (and logged the deviation deliberately). P-10
named 3. The last card that built cleanly, P-08, named exactly 2. MOSAIC's
own closing rule applies: repeated deviations of the same kind are a signal
to enforce the rule, not to keep deviating.

## Splits

| original | becomes | reason |
|---|---|---|
| P-09 | P-09a, P-09b, P-09c | 5 source files → 2, 2, 1 |
| P-10 | P-10a, P-10b | 3 source files → 2, 1 |
| P-21 | P-21a, P-21b | 3 source files (css/html/js) → markup, behaviour |
| P-25 | P-25a, P-25b | 4 files (two views) → one view each |
| P-26 | P-26a, P-26b | 3 files (main/config/window) → 2, 1 |

Letter suffixes rather than renumbering, so existing BUILD_STATE entries and
cross-card references still resolve.

## The registration line-edit convention

Several cards must add one line to a registration file — a `services/__init__.py`
slot, an `api/app.py` router include, a `ui/index.html` mount, a pinned
dependency, an IMPLS list entry. Counting those as source files would make
almost every card fail R10 for a single line of wiring.

Convention adopted here, listed explicitly on each card as `REGISTER`:

- a REGISTER file is line edits only, no logic, and no more than ~5 changed lines
- REGISTER files do not count toward the 2-source-file budget
- everything else counts

This is a deviation from a literal reading of R10 and should be logged in
BUILD_STATE.md as such. If it turns out registration edits are causing
failures too, the convention is wrong and R10 should be applied literally.

## What else changed in every card

**Explicit file roles.** `SOURCE` / `TESTS` / `REGISTER` labels make the R10
count checkable at a glance instead of requiring interpretation of a
prose list.

**A `Stop and ask if` section.** Three sessions were lost to the agent
searching the repository instead of building — repeated identical greps,
no code written. Each card now names the conditions under which the agent
should stop rather than explore, and states plainly not to survey the repo.

**A `Commit:` line.** Seven consecutive commits carried the description
"paths and value objects" because the description was copied forward by
hand. The commit text is now part of the card.

**A `Forbidden` section on every card.** MOSAIC §5 requires it; several
originals omitted it.

**Total line estimates.** Each card states its expected total, and where a
card sits near the ceiling it says so and names the split to emit if a file
grows past 300 lines.

## Audit

    card     src tst reg  lines  R10
    P-09a      2   1   0    310  PASS
    P-09b      2   1   0    330  PASS
    P-09c      1   1   1    260  PASS
    P-10a      2   1   1    380  PASS
    P-10b      1   1   1    230  PASS
    P-11       1   1   1    400  PASS
    P-12       1   1   1    330  PASS
    P-13       2   1   1    330  PASS
    P-14       2   1   1    260  PASS
    P-15       1   1   1    440  PASS
    P-16       1   1   1    360  PASS
    P-17       1   2   1    210  PASS
    P-18       2   1   1    450  PASS
    P-19       2   1   1    480  PASS
    P-20       1   2   1    460  PASS
    P-21a      2   1   0    390  PASS
    P-21b      1   1   1    280  PASS
    P-22       2   1   1    520  PASS
    P-23       2   1   1    500  PASS
    P-24       2   1   1    520  PASS
    P-25a      2   1   1    240  PASS
    P-25b      2   1   1    220  PASS
    P-26a      2   1   1    240  PASS
    P-26b      1   1   1    260  PASS
    P-27       1   1   0    150  PASS
    P-28       0   1   1    320  PASS
    P-29       2   1   1    390  PASS

    27 cards, 0 R10 failures, largest 520 lines

The four largest (P-22, P-23, P-24 at ~500-520, P-19 at 480) are UI and API
cards where the test file carries most of the weight. Each names the split
to emit if its main source file passes 300 lines. Watch these four; if any
stalls, the line budget matters as much as the file count and the remaining
UI cards should be split further.

## Open items this rewrite does not resolve

**CC-01 rests on a bad reading.** R10 genuinely says "public API of a module
≤ 7 symbols" — the earlier conclusion that this was a mislabel was wrong.
`core.errors` at 14 symbols is a real violation, and the MOSAIC-shaped
response is a portion that splits it, not a contract amendment. P-04's tests
currently encode the amendment. Worth revisiting deliberately.

**P-29's completion line.** The original said "29 cards"; elsewhere it said
21. The real count is 27 plus P-00 through P-08. Set the number when you
write the closing line.

**BUILD_STATE.md** needs the deviation log entry for the REGISTER convention
and the record of these splits.
