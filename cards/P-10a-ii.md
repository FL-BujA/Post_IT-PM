# PORTION P-10a-ii — services: project lifecycle (one call, whole world)

Goal: services/projects.py — create_project full glue and update_project.
This card carries the signature acceptance: one call builds the entire
project world.

Contract: 03-CONTRACTS-services.md (C3.1 project section)

Files allowed (R10 budget: 2 source files + their tests):
  SOURCE   services/projects.py
  TESTS    tests/svc/test_projects.py
  REGISTER services/compose.py (LINE EDIT ONLY: replace the project_svc
           placeholder with the real ProjectSVC — one line)

Context Pack: this card · the C3.1 project section of
  contracts/03-CONTRACTS-services.md · core.sig.txt for ALL core and data
  signatures. Do not open any .py file under core/ or data/ — core.sig.txt
  is complete and is the only signature source for this card.

Done when:
  - test_one_call_whole_world — create_project("Alpha Bom", "2026-09-30",
    "TBD") on a FRESH empty tmp workspace produces, in ONE call:
      * project row with status 'planned'
      * charter event present (kind 'charter', summary contains 'Alpha Bom')
      * first open cycle row named 'Charter cycle'
      * evidence/, reports/ and backups/ directories created
      * root manifest.json exists with projects: ["P001"]
      * NO evidence rows (nothing attached yet)
    This is the signature test — 00-ARCHITECTURE core acceptance, project side.
  - a duplicate code raises ServiceError with code 'project_exists'.
  - update_project: name, target and prepared_for each persist and emit an
    UPDATE event naming the changed field in the summary (parametrized x3).
  - ServiceKit(tmp).project_svc is the real ProjectSVC; the other seven slots
    still raise CoreError (one test asserts both halves — the C3.0 shape from
    P-10a-i is unchanged).

Forbidden: implementing open_cycle or close_cycle — that is P-10b. The
  'Charter cycle' row here is created through the data layer directly, not
  through phase_svc. No HTML. No reading of evidence files. No changes to
  services/compose.py beyond the single placeholder replacement line.

Stop and ask if: a signature you need is absent from core.sig.txt, or services/compose.py does not already exist with placeholder slots. In either case stop and ask — do not read source files to reconstruct the signature, and do not create compose.py yourself.

Commit: P-10a-ii: project lifecycle service

Est. size: projects.py ~140, tests ~150. Total ~290.
