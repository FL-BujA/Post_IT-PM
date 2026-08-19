# Windows 11 Memory Pressure Assistant — Scope for Codex

**Status:** Final project scope for Codex implementation  
**Purpose:** Build a Windows-native memory pressure controller, not a blind RAM cleaner.  
**Source PDF:** `Win11_Memory_Pressure_Assistant_Scope_for_Codex(2).pdf`

---

## 1. Executive Summary

| Item | Final Decision |
|---|---|
| Architecture | Windows Service + standard-user tray app communicating through local IPC. |
| Primary goal | Preserve responsiveness by detecting real memory pressure and applying guarded cleanup. |
| Main trigger philosophy | Use available RAM, commit pressure, pool memory, pagefile state, trend validation, and protected-activity gates. |
| Cleanup philosophy | Trim only safe, role-selected background processes. Avoid restarts and avoid random process termination. |
| Critical protection | Never disrupt Dell Command \| Update, Windows security, drivers, foreground work, VM/WSL workloads, or active meetings. |

---

## 2. Project Objective

Build a lightweight Windows 11-native utility that:

- Monitors memory pressure continuously.
- Performs safe cleanup only when the system shows real memory pressure.
- Works with Windows memory management instead of fighting it.
- Protects user work, Dell update workflows, system drivers, security tools, VM/WSL workloads, and active foreground applications.
- Provides measurable before/after validation and structured logs.

---

## 3. Non-Goals and Boundaries

The project shall **not**:

- Build an aggressive RAM cleaner.
- Kill random processes.
- Restart processes by default.
- Disable Windows Defender, drivers, SysMain, Dell Command | Update, or Dell Core Services.
- Modify BIOS, firmware, registry, pagefile settings, or system files by default.
- Claim to increase physical RAM.

The tool only manages memory pressure and cleanup behavior.

---

## 4. Final Architecture Decision

```text
Tray UI (standard user)
 - status display
 - pause/resume
 - manual optimize
 - settings/config editor
 - log viewer
 |
 | Local IPC
 v
Windows Service (elevated/service context)
 - monitoring
 - threshold logic
 - protected activity checks
 - cleanup execution
 - logging / event reporting
```

| Component | Responsibility | Privilege Model |
|---|---|---|
| Windows Service | Runs monitoring, threshold engine, cleanup engine, validation, anti-flapping, and logging. | Elevated/service account. |
| Tray App | Shows status, allows pause/resume/manual optimize, edits settings, and displays logs. | Standard user. Do not run elevated. |
| Installer | Installs service, tray startup entry, Event Log source, config folder, and log folder. | Admin required at install/uninstall only. |
| IPC Layer | Allows tray app to request status/actions from service. | Local-only, authenticated to current machine. |

---

## 5. Monitoring Layer

Implementation requirements:

- Use PDH / `PerformanceCounter` where practical, with approximately 5-second polling inside the service.
- Prefer official Windows counters for normalized memory pressure, especially `Memory\% Committed Bytes In Use`.
- Track process-level and system-level signals to distinguish normal caching from actual pressure or leaks.

| Metric | Purpose |
|---|---|
| Available RAM | Primary physical memory pressure indicator. |
| `% Committed Bytes In Use` | Official normalized commit pressure indicator. |
| Pagefile usage % and growth rate | Detects paging pressure and near-commit-limit risk. |
| Pool nonpaged bytes | Detects kernel memory pressure that can destabilize the system. |
| Pool paged bytes | Adds kernel pool pressure visibility. |
| Handle count per process | Detects handle leaks that may destabilize Windows even if memory looks stable. |
| GDI object count | Detects GUI resource leaks. |
| Private bytes | Best process-level view of committed private memory. |
| Working set | Shows current physical RAM residency. |
| Modified page list size | Guard before trimming; prevents forcing dirty pages toward disk. |
| Standby list size/headroom | Guard before trimming; prevents pushing pressure into paging. |
| Disk queue length | Avoid standby purge or trimming while storage is already busy. |
| Foreground process/session state | Protect active user work. |
| VM/WSL signals | Protect `vmmem`, Hyper-V, WSL, and VM workloads from normal process trimming rules. |

---

## 6. Threshold and Spike Engine

Requirements:

- Use adaptive thresholds where possible, with user override for machines such as the current 16 GB laptop.
- Use hysteresis to avoid oscillation around stage boundaries.
- Use trend validation before marking cleanup successful.
- Add spike source attribution so legitimate foreground allocations are not punished.

### Adaptive Default

```text
PressureThreshold = min(4 GB, TotalRAM x 15%)
```

### User Override for Current 16 GB Laptop

| Stage | Enter / Exit Rule |
|---|---|
| Stage 2 enter | Available RAM < 4.0 GB |
| Stage 2 exit | Available RAM > 4.8 GB for 3 cycles |
| Stage 3 enter | Available RAM < 2.5 GB OR `% Committed Bytes In Use` > 85% |
| Emergency enter | Available RAM < 2.0 GB OR `% Committed Bytes In Use` > 92% |

### Spike Override

If available RAM drops by more than 1.5 GB in less than 30 seconds:

1. Identify the source process/process tree.
2. If the source is foreground app, VM/WSL, installer, compiler, CAD, or approved workload:
   - Skip cleanup.
   - Log spike source.
3. If the source is background/orphan/non-protected:
   - Evaluate Stage 3.

---

## 7. Protected Activity Gate

Requirements:

- Cleanup shall be skipped, delayed, or reduced to logging-only when protected activity is detected.
- The gate must run before any trimming, standby purge, restart, or cleanup action.
- The tray app must provide manual pause/resume and manual optimize controls.

| Protected Activity | Expected Handling |
|---|---|
| Video call / screen sharing | Skip cleanup or reduce to logging-only. |
| Full-screen app / presentation mode | Skip cleanup unless emergency and safe action only. |
| Installer / Windows Update | Skip cleanup. |
| Dell Command \| Update running/installing | Skip cleanup and retry next cycle. |
| Game Mode / high GPU rendering | Skip cleanup to avoid stutter. |
| Sleep / resume transition | Suspend monitoring actions; avoid wake loops. |
| VM/WSL active workload | Protect by default; log but do not trim. |
| Foreground high-memory allocation | Attribute spike; skip cleanup if source is legitimate active work. |

---

## 8. Dell Command | Update Protection

Requirements:

- The tool must explicitly preserve Dell Command | Update and related update services.
- If any Dell update process, service, or lock indicator is active, cleanup must be skipped and logged.
- This protection is required because Dell Command | Update is the user-approved path for BIOS, firmware, and driver updates.

### Never Touch

- `DellCommandUpdate.exe`
- `DellUpdate*`
- `DellClientManagementService`
- `Dell Command | Update for Windows Universal`
- `Dell Core Services`
- Dell update installation folders or lock files

### Rule

```text
If Dell Command | Update is active or installing,
skip cleanup and retry next cycle.
```

---

## 9. Cleanup Engine

Requirements:

- Use role-based process selection instead of name-only allowlists.
- Treat working-set trimming as guarded and moderate-risk, not automatically low-risk.
- Do not restart or kill processes by default.
- Only purge standby list under confirmed pressure and only when disk and memory-list conditions are safe.

| Process Role | Default Action |
|---|---|
| Foreground process | Protect. |
| Child of foreground process | Usually protect. |
| Background process idle for > N minutes | Candidate if other guards pass. |
| Orphan/background helper process | Candidate if other guards pass. |
| High private bytes and background | Candidate if other guards pass. |
| VM/WSL process | Special handling; protect by default. |
| System/vendor protected process | Never touch. |

A process may be considered for trimming only if:

```text
PrivateBytes > configured threshold
AND process has been background for > N minutes
AND process is not foreground
AND process is not child-of-foreground
AND process is not protected
AND standby headroom is sufficient
AND modified page list is not already high
AND disk queue length is low
AND the system is not under active paging pressure.
```

---

## 10. Cleanup Stages

| Stage | Enter Condition | Allowed Actions | Exit Condition |
|---|---|---|---|
| Stage 1 — Observe | Normal monitoring or pressure not confirmed. | Log memory, commit, pool, handles/GDI, top processes, protected activity. No cleanup. | N/A |
| Stage 2 — Guarded trim | Available RAM below Stage 2 threshold, with hysteresis rules satisfied. | Trim role-approved background processes only if standby/headroom guards pass. Clear safe temp/cache only if configured. | Available RAM above Stage 2 exit threshold for 3 cycles. |
| Stage 3 — Confirmed pressure | Available RAM < 2.5 GB OR commit pressure > 85%, and protected gate allows action. | Stage 2 plus optional standby purge only if disk idle, commit pressure is high, and standby/modified lists are safe. | Stable recovery for 3 cycles. |
| Emergency | Available RAM < 2.0 GB OR commit pressure > 92%. | No restarts. Log top 5 private-bytes processes. Trim only approved safe targets. Optional standby purge only if safe. | Stable recovery for 3 cycles. |

---

## 11. WSL, Hyper-V, and VM Guard

Virtualized workloads consume memory differently from normal desktop apps.

Requirements:

- Exclude virtualized workloads from default trimming.
- Treat them as protected unless the user explicitly enables a VM/WSL policy.
- The tool may log these processes as pressure sources but must not trim them by default.

### Protect by Default

- `vmmem.exe`
- `vmmemWSL.exe`
- `vmwp.exe`
- `wslhost.exe`
- `VirtualBoxVM.exe`
- `vmware-vmx.exe`

---

## 12. Validation and Anti-Flapping

Requirements:

- After cleanup, wait 60–90 seconds before judging the result.
- Require 2 consecutive readings showing improvement before marking cleanup successful.
- Require available RAM to remain above the recovery threshold for 3 cycles before considering the system stable.
- Use exponential backoff after ineffective cleanup attempts.

### Backoff Sequence After Ineffective Cleanup

```text
30 minutes -> 1 hour -> 2 hours -> 4 hours
```

Reset backoff only after 3 successful idle/stable cycles.

---

## 13. Logging and Telemetry

Requirements:

- Use structured JSON logs and a Windows Event Log source named `Win11MemAssist`.
- Rotate logs at 50 MB and archive older logs.
- Log fully on threshold crossing, cleanup, emergency, errors, privilege denial, and recovery.
- Use reduced logging during backoff so logs remain useful and do not mask important events.

| State | Logging Behavior |
|---|---|
| Normal monitoring | Low-frequency summary log. |
| Threshold crossed | Full diagnostic log. |
| Cleanup performed | Full before/after log. |
| Backoff active | Reduced log rate; log only state changes, errors, threshold crossings, and recovery. |
| Emergency | Full diagnostic log. |
| Error / privilege denied | Full diagnostic log. |

### Minimum Log Fields

- Timestamp
- Available RAM
- `% Committed Bytes In Use`
- Compressed memory
- Pagefile usage and growth
- Paged pool / non-paged pool
- Handle count / GDI object count
- Disk queue length
- Top processes by private bytes
- Top processes by working set
- Protected activity status
- Trigger reason
- Cleanup stage
- Actions performed
- Before/after result
- Success/failure
- Errors
- Backoff status

---

## 14. Configuration Requirements

Requirements:

- Use a JSON configuration file controlled by the service and edited through the tray app.
- Include protected processes, approved trimming rules, thresholds, hysteresis values, and logging settings.
- Validate config before applying changes.
- Invalid config should be rejected and logged.

### Example Config Concept

```json
{
  "stage2AvailableGb": 4.0,
  "stage2ExitAvailableGb": 4.8,
  "stage3AvailableGb": 2.5,
  "emergencyAvailableGb": 2.0,
  "commitPressureStage3Percent": 85,
  "commitPressureEmergencyPercent": 92,
  "privateBytesTrimThresholdMB": 300,
  "backgroundMinutesBeforeCandidate": 10,
  "enableVmWslTrimming": false,
  "protectedProcesses": [
    "DellCommandUpdate.exe",
    "DellUpdate*",
    "MsMpEng.exe",
    "dwm.exe",
    "explorer.exe",
    "vmmem.exe",
    "vmmemWSL.exe"
  ]
}
```

---

## 15. Installer and Privilege Design

| Item | Requirement |
|---|---|
| Windows Service | Installed with admin rights and configured to start with Windows. |
| Tray App | Installed as standard-user startup entry. Must not run elevated. |
| Event Log Source | Create `Win11MemAssist` source at install time. |
| Config Directory | Create with appropriate ACLs. |
| Log Directory | Create with rotation and archival policy. |
| Privileges | Document and request only what is required. Handle denied privileges gracefully. |

Additional requirements:

- Required privileges to document:
  - `SeDebugPrivilege`
  - `SeIncreaseQuotaPrivilege`
- The service performs privileged cleanup actions; the tray app requests actions through IPC.
- Install/uninstall requires admin rights.
- Normal daily use should not generate UAC prompts.

---

## 16. Implementation Roadmap for Codex

| Phase | Deliverables |
|---|---|
| Phase 1 — Core Engine | Windows Service skeleton, PDH/PerformanceCounter monitoring, adaptive thresholds, hysteresis, JSON config, Dell update protection, structured logs. |
| Phase 2 — Cleanup Engine | Role-based process classification, guarded working-set trimming, standby/headroom checks, Stage 2/3/Emergency behavior. |
| Phase 3 — Safety Layer | Protected activity gate, VM/WSL guard, spike source attribution, sleep/resume handling, disk idle gate. |
| Phase 4 — Validation + Anti-Flap | Post-cleanup validation, 3-cycle stability, exponential backoff, reduced logging during backoff. |
| Phase 5 — Tray UI | Status, pause/resume, manual optimize, settings editor, log viewer, local IPC integration. |
| Phase 6 — Installer | Install service, tray startup, Event Log source, config/log directories, clean uninstall. |

---

## 17. Codex Implementation Instructions

Codex shall:

- Start with the service, monitoring layer, and logging before implementing cleanup.
- Not implement aggressive standby purge first.
- Guard cleanup using headroom, disk idle, protected activity, and process role checks.
- Implement all cleanup behavior as dry-run capable before enabling real actions.
- Use feature flags/config for risky actions, especially standby purge and VM/WSL handling.
- Keep tray UI separate from service logic.
- Avoid placing core cleanup logic in the tray app.
- Ensure every cleanup action produces before/after telemetry and a clear reason code.
- Keep default behavior conservative and safe.

---

## 18. Acceptance Criteria

The implementation is acceptable when:

- Service runs continuously with target footprint below approximately 30 MB RAM and below 0.5% CPU during idle monitoring.
- Tray app runs as standard user and can pause/resume monitoring, request manual optimize, and display current state.
- Dell Command | Update is never interrupted during update checks or installations.
- Protected activity gate prevents cleanup during calls, full-screen work, updates, sleep transitions, and VM/WSL activity by default.
- Stage boundaries use hysteresis and do not oscillate around thresholds.
- Working-set trimming never occurs without standby/headroom and modified-page-list checks.
- Standby purge only occurs in Stage 3/Emergency and only when disk is idle and memory pressure is confirmed.
- All actions are logged with before/after telemetry and result status.
- Backoff prevents repeated ineffective cleanup loops.
- The tool can run in dry-run mode for validation before enabling cleanup actions.

---

## 19. Final Consensus

| Topic | Final Agreement |
|---|---|
| Agreed scope | Build a Windows 11-native Memory Pressure Assistant using a Windows Service plus tray UI. |
| Key decisions | Monitor pool memory, handles, GDI objects, pagefile utilization, standby headroom, and modified page list size. Use role-based process selection, VM/WSL protection, stage hysteresis, guarded trimming, and structured telemetry. |
| Most important pre-code decisions | Use service + tray architecture and implement standby/headroom checks before any process trimming. |
| Primary implementation posture | Conservative by default, dry-run capable, telemetry-first, with cleanup enabled only after guarded logic is validated. |
