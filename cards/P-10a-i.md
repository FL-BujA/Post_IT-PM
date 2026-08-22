# PORTION P-10a-i — services: ServiceKit skeleton (placeholder slots only)

Goal: services/compose.py — create the services package and the ServiceKit
class with the full C3.0 attribute set. EVERY slot is a typed placeholder that
raises CoreError. No real service logic in this card at all.

This card exists to create the services/ directory and freeze the C3.0
attribute set before any service is written, so later cards extend an existing
package instead of inventing one.

Contract: 03-CONTRACTS-services.md (C3.0 composition — the attribute list only)

Files allowed (R10 budget: 2 source files + their tests):
  SOURCE   services/compose.py
  TESTS    tests/svc/test_compose.py
  REGISTER services/__init__.py (CREATE: the package file, re-export
           ServiceKit, nothing else)

Context Pack: this card · the C3.0 attribute list from
  contracts/03-CONTRACTS-services.md — nothing else. This card needs NO
  signatures from core or data. Do not look any up.

Done when:
  - services/ exists as a package with __init__.py re-exporting ServiceKit.
  - ServiceKit(root) accepts a workspace root path and stores it. It does not
    open a database, create directories, or touch the filesystem.
  - ServiceKit exposes every slot named in C3.0: project_svc, phase_svc,
    actions_svc, evidence_svc, minutes_svc, report_svc, backup_svc,
    integrity_svc. Each is an instance of a small typed placeholder class.
  - every placeholder raises CoreError with a message naming the slot when
    ANY attribute on it is accessed (parametrized test over the eight slot
    names — the test asserts CoreError and that the message contains the
    slot name).
  - test_c30_attribute_set — one test asserts the complete attribute set by
    name. From this card onward the C3.0 shape is frozen; later cards replace
    placeholders, never add or rename slots.

Forbidden: implementing any real service; importing anything from data/;
  reading any file under core/ or data/; creating directories or a database;
  touching any card or contract other than the two named above.

Stop and ask if: services/ already exists with content, or the C3.0 attribute list cannot be found in contracts/03-CONTRACTS-services.md after ONE read. Do not search for it elsewhere — stop and ask.

Commit: P-10a-i: ServiceKit skeleton with placeholder slots

Est. size: compose.py ~70, __init__.py ~5, tests ~70. Total ~145.
