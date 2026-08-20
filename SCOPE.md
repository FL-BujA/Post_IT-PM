# PROJECT SCOPE — PM COCKPIT (working title, rename freely)

**Version:** 0.2 — all open questions resolved; ready for sign-off
**Product Owner:** [NAME — the PM]
**Sponsor:** [open field — filled in by the PM at sign-off / report generation]
**Status:** READY FOR SIGN-OFF
**Last updated:** 2026-08-19
**Deadline (fixed, confirmed):** 2026-08-31

> Scope discipline: this document is the source of truth for what v1 is and is NOT.
> The deadline is fixed; THIS page is the variable that flexes.
> Any change after sign-off requires a swap: what enters names what leaves. The PO decides.

---

## 1. Purpose

One local place on the PM's laptop where the project's story, evidence, actions, and status live — so that:

- Any decision can be explained on demand with attached evidence ("Why did we buy the most expensive one?" → the technical-evaluation email, attached, no searching).
- The loop charter → actions → priorities → execution → gates → next cycle is driven visually.
- Sponsors and stakeholders get a credible one-page report.
- Team engagement is visible, including "asks for more time" as recorded data.
- Team meetings are driven by the tool on screen share instead of slides, and minutes live inside the timeline.

Benefited: PM (daily driver), sponsors/stakeholders (report), project team (meetings run from the same screen).

## 2. Problem Statement (plain language, no softening)

- Project management without clear target dates, deliverables, or well-defined gates.
- Consequence: sponsor/stakeholder communication degrades; unmanaged expectations become frustration.
- Root cause: no single artifact where decisions, their evidence, and status live; "done" is undefined; engagement signals (asks for more time) stay informal conversations instead of data.
- Starting condition, accepted not debated: the deadline is fixed and close. Scope is what flexes.

## 3. Scope Summary (one paragraph)

PM Cockpit is a single-user desktop application running locally on the PM's Windows laptop — no server, no web, no internet dependency. It manages multiple projects, each flowing: project → charter → action plan → priorities → execution → verification gates → next priority cycle (loop) → delivery → documentation & handover → finished. It ingests evidence files (spreadsheets, screenshots, emails as PDF) and attaches them to timeline items, decisions, and actions, so the project reads as one chronological story. It runs the priority loop on a visual action board, records extension/defer requests as engagement signals, and generates a professional one-page PDF report (target, status, current priorities, red flags, escalation) for sponsors and stakeholders. Parallel to the flow: continuous evidence capture, meeting minutes, and reporting until project completion.

## 4. IN SCOPE — v1 (top 3; confirmed by PM 2026-08-19 — no objection raised after proposal)

Rule: v1 = the top 3 that prove the core flow works end-to-end. Everything else is parked.

| # | Feature / Flow | Why it earns v1 | Target |
|---|----------------|-----------------|--------|
| 1 | Project + timeline + evidence: create project, write charter, attach any file type (xlsx/png/jpg/PDF/email-as-PDF) to items, chronological story view, search and retrieve | This is the core: "tell the story" and explain-any-decision-on-demand | M1 |
| 2 | Actions & priorities: define actions (owner, priority, due), visual priority ranking per cycle, validate, status tracking, defer/extension requests logged as engagement signals | The management loop + engagement visibility | M1→M2 |
| 3 | One-page PDF report: project target, status (RAG), current priorities, red flags, escalation topics — visual, professional, generated from live data | Sponsor/stakeholder communication is the stated failure | M2 |

**Supporting in-scope elements (not optional):**

- Multi-project from day 1: list / create / switch / archive; data model is namespaced per project; demo dataset contains 2 projects.
- Meeting minutes: log a meeting as a timeline item; decisions captured; each decision can spawn a linked action in one click.
- Correction behaviour on every flow: cancel / retry / resume (edit a decision → revision recorded, original kept; cancel → resume an action; regenerate a report without destroying the previous one).
- Backup & restore from day 1 (export all / import all, checksummed).
- Demo dataset with real-shape data for acceptance.

## 5. OUT OF SCOPE

**Excluded permanently (by design — not revisited as features):**

- Web hosting, server deployment, any internet dependency.
- Multi-user, shared access, or direct team usage. Confirmed model: PM cockpit — the team never touches the tool; the PM is the single data entrant, and drives meetings by screen share.

**Parking Lot (re-enter only as a swap, decided by PO at milestone review):**

| # | Item (as raised) | Re-entrance condition | Revisit at |
|---|-----------------|-----------------------|------------|
| 1 | Gantt-style scheduling view | swap-named, PO approves | after M2 |
| 2 | Auto-ingestion from email inbox / shared drives | swap-named, PO approves | after M2 |
| 3 | Budget ledger / cost calculation (v1: costs are evidence only) | swap-named | after M2 |
| 4 | Mobile / second-screen views (screen share suffices for v1) | swap-named | after M2 |

## 6. SIPOC / System Boundary

- **Suppliers:** the PM (files, text, priorities).
- **Inputs:** evidence files (xlsx, png/jpg, PDF, email-as-PDF); charter text, targets, key dates; actions, owners, priorities, dues; meeting minutes text.
- **Process:** PM Cockpit (local app).
- **Outputs:** timeline story, visual priority board, engagement log, one-page PDF report, backup package.
- **Customers:** PM; sponsors/stakeholders (via report); project team (via screen-shared meetings).
- **First step:** open app → select or create project. **Last step:** generate/attach the one-page report and/or archive the project with handover documentation.

## 7. Deliverables

| ID | Deliverable |
|----|-------------|
| D1 | Windows desktop application (local, single-user) |
| D2 | Local project data store with backup/restore (zip export/import, checksummed) |
| D3 | One-page PDF report generator (5 mandated blocks, professional layout) |
| D4 | Two demo projects populated with real-shape data (acceptance evidence) |
| D5 | Handover documentation: README (how to use, where data lives, backup procedure) |

## 8. Requirements

### 8.1 Functional

- **F1 Multi-project:** create, list, switch, archive; all data namespaced per project.
- **F2 Project flow:** project carries a charter (targets, target dates, key dates); flow steps are visible; transitions between steps are explicit, never implicit.
- **F3 Evidence:** attach any file type to a timeline item, decision, or action; original stored unmodified; retrieve with a click; search by text where extractable, by metadata always.
- **F4 Timeline:** chronological view over all project items (events, decisions, actions, meetings, gates); each item shows date, type, status; decisions show their linked evidence.
- **F5 Actions:** create with description, owner (name), priority, due; states open / in progress / done / deferred / cancelled. Engagement signals are first-class events, three types: (a) **defer/extension request** — explicit, with date + reason; (b) **late start** — start slips past the committed start/due date, recorded with a note; (c) **reopen** — a done action returns to in progress; the tool counts reopens per action and flags **repeated reopens (≥2)**. The engagement log groups all three signal types by owner and by type; signals are visible in the report.
- **F6 Priorities:** per-cycle priority list; visual ordering; PO validation (approved/not) recorded with date.
- **F7 Gates:** verification gates defined with checklist items; pass/fail; passing requires linked evidence.
- **F8 Report:** one-page PDF containing: project target, status (RAG), current priorities, red flags, escalation topics, and a compact **engagement/health strip** (defer/extension requests, late starts, reopens — grouped by owner); generated from live data; regenerable without destroying prior versions; stamped with project name + generation date; **"Prepared for:" (sponsor) field filled by the PM at generation time** (sponsor is a free field per Q2); design follows PRISM_UI_Protocol (N4).
- **F9 Meeting minutes:** log a meeting as a timeline item; decisions listed; each decision can create a linked action; minutes searchable.
- **F10 Search:** cross-project retrieval over items, evidence metadata, and minutes — the "no need to search anywhere else" property.
- **F11 Data handling:** export-all (backup) and import-all (restore); committed records are never silently overwritten — edits create revisions, originals retained.

### 8.2 Non-functional

- **N1:** Windows; single user; no server; no internet required.
- **N2:** launches in under 3 seconds on a mainstream laptop; 1,000+ attached files do not degrade search or open time (proposed standard).
- **N3:** professional, screen-share-ready UI — large and legible in a video call; one screen per job; no modal walls.
- **N4:** UI construction follows **PRISM_UI_Protocol** as the governing design reference (supplied by the PM; see A6), applied as a reference — consistent theme, tokens, and component behaviour. Folder memory: app remembers where each project's data lives, never prompts again.
- **N5:** every mutating action is correctable (cancel / retry / resume); nothing irreversible without explicit confirmation.
- **N6:** data integrity: checksum on evidence files; restore validates before replacing.

## 9. Inputs

| Type | Source | Rule |
|------|--------|------|
| Evidence files (xlsx, png, jpg, PDF, email-as-PDF) | PM's files / mailbox | original stored unmodified; name, type, attach-date recorded |
| Charter text, targets, key dates | PM entry | structured fields |
| Actions, owners, priorities, dues | PM entry | owners are free-text names |
| Meeting minutes | PM entry | meeting name, date, decisions, actions |

## 10. Outputs

Timeline story (on screen) · visual priority board (on screen) · engagement log (on screen + in report) · one-page PDF report (saved file) · backup zip (saved file).

## 11. Workflow (happy path + correction)

**Main flow:** open app → select/create project → write charter → define actions → set and validate priorities → execute: update action states, attach evidence to items, run gate checklists → gate pass → next priority cycle (LOOP) → delivery → documentation & handover → archive.

**Parallel lanes (active until completion):** evidence capture, meeting minutes, periodic one-page reporting.

**Correction paths:**
- Action cancelled → resumed; both events in history.
- Decision edited → revision recorded with reason; original linked, not destroyed.
- Gate failed → actions generated from failed items.
- Report regenerated → previous version retained.

## 12. UI/UX

**Governing reference: PRISM_UI_Protocol** — UI construction applies this protocol as its design reference (theme, layout, component behaviour, visual language). Status: reference supplied as a baseline, not a pixel-for-pixel mandate — where a PM cockpit workflow conflicts with a protocol rule, the workflow wins and the deviation is noted in build log (see A6).

- Timeline is the spine; **story-first** chronological flow (confirmed — Gantt remains Parking Lot #1). Side rail: Projects · Actions · Priorities · Minutes · Engagement · Report.
- RAG status on project, gates, and actions.
- Priority board: visual ranking with a validation stamp (approved + date).
- Screen-share ready: large type, minimal clutter (video-call legibility).
- One primary action per screen.
- Engagement view: signals grouped by owner and type (defer/extension, late start, reopen/repeated reopen) — the at-a-glance "who is struggling" screen.

## 13. Data & Traceability

- Every item: ID, timestamp, actor (PM), revision history.
- Evidence: filename, type, size, checksum, attach date, linkage target.
- Decision → evidence links, visible from both sides.
- Audit log: create / edit / status change / cancel / restore.
- Committed records are never silently overwritten.

## 14. Assumptions (each is a risk if it breaks — owner + verify date)

| ID | Assumption | Owner | Verify by |
|----|-----------|-------|-----------|
| A1 | Deadline is 08/31/2026 (the "08/31/2016" entry is presumed a typo) | PM | 08/19 — Q1 |
| A2 | 12-day build is feasible only if v1 stays at top 3 (section 4) — **re-check required**: engagement signals broadened to three types at PO direction (Q5); if the build agent shows slippage by M1, the FIRST scope to shed is the engagement health strip in the report (not the signal capture) | PM | M1 review |
| A3 | The build agent (Qwen 3.8_27b + OpenHands) executes on the target Windows machine | PM | 08/20 — **BLOCKER #1 if NO** |
| A4 | Team never uses the tool; PM is the single operator (confirmed) | PM | — |
| A5 | All data is local; backup responsibility sits with the PM (tool provides export/restore) | PM | — |
| A6 | PRISM_UI_Protocol document (or a link to it) is in the PM's possession and can be handed to the build agent before build day 1 | PM | 2026-08-20 — if not available, fall back to free professional design per N3 (PO decides at M0; a mid-build theme is a 2-week rework, so the decision is made ONCE at M0) |

## 15. Constraints

Windows OS · local only · single user · fixed deadline 08/31/2026 · built by AI agent (Qwen 3.8_27b + OpenHands) — the build toolchain must run on the target machine · no server, no internet dependency.

## 16. Risks & Controls

| # | Risk | Likelihood | Impact | Owner | Control |
|---|------|-----------|--------|-------|---------|
| R1 | Build slip (12 days is tight for a new app) | High | High | PM + build agent | thin spine first · visible increment every day · per-milestone demo |
| R2 | OpenHands/tooling friction on Windows (A3) | Medium | High | PM | verify 08/20; if NO, decide same day: WSL/VM fallback or rebaseline |
| R3 | Scope creep (minutes, Gantt, ingestion) re-enters mid-build | High | High | PM (PO) | swap-or-nothing rule; Parking Lot section 5 |
| R4 | Data loss before backup exists | Low | High | PM | backup/restore from day 1 (F11); restore verified at M3 |
| R5 | PRISM_UI_Protocol reference lands mid-build, after UI patterns are set | Medium | Medium | PM | protocol in hand or explicitly waived by 08/20 (A6/M0); theme decided ONCE at M0 |

**Build rhythm (M0–M3):** every day the agent delivers a visible increment; the PM reviews it the same day. No silent multi-day work without a check-in.

## 17. Acceptance Criteria (testable)

- **AC1 (flow 1):** create a project, write its charter, attach 3 different file types including an email-as-PDF; the timeline shows everything in chronological order; the PDF opens from the timeline; a keyword search in minutes finds the decision and jumps to its evidence. Pass: zero manual file hunting.
- **AC2 (flow 2):** 5 actions across 2 owners; priorities ranked and validated; at least one example of EACH engagement signal type recorded — a defer/extension request (with reason), a late start, and one action reopened twice (repeated-reopen flag raised); the engagement view groups signals by owner and type.
- **AC3 (flow 3):** one-page PDF generated; contains project target, status RAG, current priorities, red flags, escalation topics; visually professional and fits one page (overflow = fail).
- **AC4 (data):** close and reopen the app — all data intact; export backup, restore to a second location, checksums match.
- **AC5 (correction):** cancel an action, then resume it; edit a decision — revision recorded, original retained.

## 18. Resolved Questions (all answered 2026-08-19)

| Q | Question | Resolution |
|---|----------|------------|
| Q1 | Deadline: "08/31/2016" — typo? | **2026-08-31 confirmed.** |
| Q2 | Sponsor name | **Open field.** Sponsor is not pre-named: the PO/PM fills the sponsor field per project when generating/attaching reports and at sign-off. The report block "Prepared for:" is filled at generation time. |
| Q3 | Timeline style | **Story-first** (chronological story spine; Gantt stays in the Parking Lot). |
| Q4 | Report theme / brand | **PRISM_UI_Protocol as the UI design reference** — applied at the UI-construction level (see Section 12, N4, A6). |
| Q5 | Engagement signals in v1 | **All three: defer/extension requests, late starts, repeated reopens.** (Broadened from the initial recommendation — see A2 re-check.) |

## 19. Phase Boundaries + Fixed Milestones (Program layer)

| Phase | Included | Excluded | Exit criteria (evidence) |
|-------|----------|----------|--------------------------|
| P1 spine | F1, F2, F3, F4, F10, F11 | actions, priorities, report | AC1 demonstrated live |
| P2 management | F5, F6, F7, F9 | report | AC2 demonstrated live |
| P3 reporting | F8 + engagement signals in report | parking-lot items | AC3 + full DoD, M2 evidence |

| Milestone | Definition (evidence, not slides) | Owner | Date |
|-----------|-----------------------------------|-------|------|
| M0 | Sign-off: scope signed (v0.2), Q1–Q5 resolved, A3 verified on the Windows machine, **PRISM_UI_Protocol in hand by the build agent — or explicitly WAIVED in writing by the PO (A6)** | PM | 2026-08-20 |
| M1 | Working demo: AC1 live (project → evidence → story) | PM | 2026-08-24 |
| M2 | UAT: PM runs a real project end-to-end; AC1–AC5 pass against DoD | PM | 2026-08-27 |
| M3 | Handover: backup/restore verified off-machine, D5 delivered, final report generated | PM | 2026-08-31 |

**Milestone gate rule:** no milestone closes on a description. It closes on a live demonstration against the named acceptance criteria.

## 20. Definition of Done

A milestone/Increment is done when ALL hold:
- [ ] Its acceptance criteria pass as a live demo, not a description
- [ ] It runs on the actual Windows laptop with real-shape data
- [ ] Correction behaviour (cancel / retry / resume) demonstrated
- [ ] Backup exported and restored to a second location, checksum matched
- [ ] Data intact after close/reopen
- [ ] Handover README present (from P1 onward)

**90% is 0%.** Work that does not meet this bar is not part of the Increment.

## 21. Final Recommendation

Directly: 2026-08-31 holds — but only under (a) top-3 scope, (b) a visible build increment every single day on the Windows machine, and (c) A3 verified by 08/20. If A3 fails, 08/20 is a DECISION day (WSL/VM fallback or rebaseline), not a working day. Two conditions close out the file now, both due 08/20 (M0): **(1) PRISM_UI_Protocol in the build agent's hands — or an explicit written waiver** (a mid-build theme decision is a two-week rework, so it is decided exactly once), and **(2) the PO name in the sign-off block** (sponsor may remain open per project, the PO may not). Sign on M0 and the build order starts the next morning.

## Change Management

- New idea → Parking Lot (section 5) with date. Discussion ends.
- Change to v1 scope → PO approves a SWAP (names what enters AND what leaves).
- Change to a milestone DATE → sponsor decision, logged with reason.

| Date | Change | Approved by | What was swapped |
|------|--------|-------------|------------------|
| 2026-08-19 | v0.1 draft created from interview | — | — |
| 2026-08-19 | v0.2: Q1–Q5 resolved (deadline 2026-08-31; sponsor = open field; story-first; PRISM_UI_Protocol as UI design reference; engagement = three signals incl. late starts + repeated reopens). F5 broadened to three signal types; F8 gains engagement strip + "Prepared for" field; N4 + Section 12 bound to PRISM_UI_Protocol; A6 + R5 added; DoD/A2 re-check noted. | PM | None — all changes are confirmations of previously proposed items, except engagement signals (broadened per PM direction; shed-order protection added in A2) |

## Sign-off

| Role | Name | Date |
|------|------|------|
| Sponsor | [NAME] | |
| PM / Product Owner | [NAME] | |
