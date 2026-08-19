# Codex Implementation Prompt

Build the Windows 11 Memory Pressure Assistant according to `SCOPE.md`.

## Source of Truth

Use these repository files as the implementation reference:

- `SCOPE.md`
- `README.md`
- `TODO.md`
- `CHANGELOG.md`

## Core Rule

Do not implement behavior outside `SCOPE.md` unless it is first proposed and accepted.

## Implementation Priorities

1. Start with the Windows Service skeleton.
2. Add monitoring and structured logging.
3. Add JSON configuration.
4. Add threshold and hysteresis logic.
5. Add Dell Command | Update protection.
6. Add dry-run cleanup logic.
7. Add guarded cleanup only after validation logic exists.
8. Add tray UI after service logic is stable.
9. Add installer last.

## Safety Rules

- Do not kill random processes.
- Do not restart processes by default.
- Do not disable Windows services.
- Do not touch Dell Command | Update, Windows security, drivers, VM/WSL workloads, or foreground applications.
- Cleanup must be conservative, logged, reversible where possible, and dry-run capable.

## Required Development Behavior

- Update `CHANGELOG.md` after meaningful changes.
- Update `TODO.md` when work is completed or new gaps are discovered.
- Keep core logic out of the tray app.
- Keep service logic testable.
- Every cleanup action must include a reason code and before/after telemetry.
