"""services.report — ReportService (card A-09).

C3.5: the one-page status report the PM hands to a sponsor.

Two pieces:
  _payload  assembles ReportPayload from the data snapshot plus engagement
            health, and computes the five frozen red-flag rules
  generate  renders it, writes html then pdf, records the row, emits the
            event — in that order, because the html is the source of record

The renderer is the C3.6 seam. This service never writes html itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core import CoreError, GateOutcome, PdfError, SignalKind
from core.hash import sha256_bytes
from data import (
    ActionRow,
    CycleRow,
    DataKit,
    ProjectRow,
    ReportRow,
    SignalRow,
)
from data.migrate import migrate
from services.engagement import EngagementService, OwnerHealth

#: C3.5 frozen limits.
MAX_PRIORITIES = 5
MAX_ESCALATIONS = 3

#: RF-3 window, and RF-4 threshold.
RECENT_SIGNAL_DAYS = 14
REPEATED_REOPEN = 2

#: RF-5: a cycle open longer than this is stalled.
STALLED_CYCLE_DAYS = 30

#: Signal kinds that escalate (C3.5 frozen).
ESCALATING_KINDS = (SignalKind.EXTENSION_REQUEST, SignalKind.REOPEN)

#: Action statuses that count as live work.
LIVE_STATUSES = ("open", "in_progress")

#: Where reports are written, relative to the workspace root.
REPORTS_DIR = "reports"


@dataclass(frozen=True)
class RedFlag:
    """C3.5 RedFlag — (code, detail, ref). Computed, never stored."""

    code: str
    detail: str
    ref: Any = None


@dataclass(frozen=True)
class ReportPayload:
    """C3.5 ReportPayload — everything the page needs, nothing more."""

    project: ProjectRow
    status: str
    target_date: str | None
    current_cycle: CycleRow | None
    priorities: list[ActionRow] = field(default_factory=list)
    red_flags: list[RedFlag] = field(default_factory=list)
    escalations: list[SignalRow] = field(default_factory=list)
    health: list[OwnerHealth] = field(default_factory=list)
    prepared_for: str | None = None


def _as_date(value: str | None) -> datetime | None:
    """Parse an ISO date or datetime string, tolerating either form."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class ReportService:
    """C3.5 ReportService — payload in, artifact on disk."""

    def __init__(self, workspace_root: str, renderer: Any) -> None:
        self._root = workspace_root
        self._renderer = renderer
        self._data: DataKit | None = None
        self._engagement = EngagementService(workspace_root)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'report' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        if self._data is None:
            db_path = os.path.join(self._root, "app.db")
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    # -- red flags (C3.5 frozen rules) -------------------------------------

    def _red_flags(
        self,
        actions: list[ActionRow],
        gates: list[Any],
        signals: list[SignalRow],
        current_cycle: CycleRow | None,
        now: datetime,
    ) -> list[RedFlag]:
        flags: list[RedFlag] = []

        # RF-1 any open/in_progress action past its due date
        for a in actions:
            if str(a.status) not in LIVE_STATUSES:
                continue
            due = _as_date(a.due)
            if due is not None and due < now:
                flags.append(
                    RedFlag("RF-1", f"{a.description} is late (due {a.due})")
                )

        # RF-2 any gate FAILED or SKIPPED in the current cycle
        for g in gates:
            if str(g.outcome) in (
                GateOutcome.FAILED.value,
                GateOutcome.SKIPPED.value,
            ):
                flags.append(
                    RedFlag("RF-2", f"gate {g.name} is {g.outcome}")
                )

        # RF-3 unresolved escalating signal within the last 14 days
        cutoff = now - timedelta(days=RECENT_SIGNAL_DAYS)
        for s in signals:
            if s.resolved:
                continue
            if str(s.kind) not in [k.value for k in ESCALATING_KINDS]:
                continue
            when = _as_date(s.occurred_at)
            if when is not None and when >= cutoff:
                flags.append(
                    RedFlag("RF-3", f"{s.kind} unresolved for {s.owner}")
                )

        # RF-4 an action reopened twice or more
        for a in actions:
            if a.reopen_count >= REPEATED_REOPEN:
                flags.append(
                    RedFlag(
                        "RF-4",
                        f"{a.description} reopened {a.reopen_count} times",
                    )
                )

        # RF-5 the current cycle has been open longer than 30 days
        if current_cycle is not None and current_cycle.closed_at is None:
            opened = _as_date(current_cycle.created_at)
            if opened is not None and (now - opened).days > STALLED_CYCLE_DAYS:
                flags.append(
                    RedFlag(
                        "RF-5",
                        f"cycle {current_cycle.name} open "
                        f"{(now - opened).days} days",
                    )
                )

        return flags

    # -- C3.5 --------------------------------------------------------------

    def _payload(
        self, project_code: str, prepared_for: str | None = None
    ) -> ReportPayload:
        """Assemble the frozen content contract for one project."""
        kit = self._ensure_data()
        project = kit.projects.get(project_code)     # raises if unknown
        now = datetime.now(tz=timezone.utc)

        current = kit.cycles.current_for(project_code)
        actions = kit.actions.list_for(project_code)
        gates = kit.gates.list_for(project_code)
        signals = kit.signals.list_for(project_code)

        priorities = sorted(
            (a for a in actions if str(a.status) in LIVE_STATUSES),
            key=lambda a: a.priority,
        )[:MAX_PRIORITIES]

        escalations = sorted(
            (
                s
                for s in signals
                if not s.resolved
                and str(s.kind) in [k.value for k in ESCALATING_KINDS]
            ),
            key=lambda s: s.occurred_at,
            reverse=True,
        )[:MAX_ESCALATIONS]

        return ReportPayload(
            project=project,
            status=str(project.status),
            target_date=project.target_date,
            current_cycle=current,
            priorities=priorities,
            red_flags=self._red_flags(actions, gates, signals, current, now),
            escalations=escalations,
            health=self._engagement.health_by_owner(project_code),
            prepared_for=prepared_for
            if prepared_for is not None
            else project.sponsor,
        )

    def generate(
        self, project_code: str, prepared_for: str | None = None
    ) -> ReportRow:
        """Render, write, record, emit — in that order.

        The html is the SOURCE OF RECORD and is kept on disk even when the
        pdf step fails; in that case no row is recorded and no event is
        emitted, and PdfError propagates (C3.5).
        """
        payload = self._payload(project_code, prepared_for)
        kit = self._ensure_data()

        date = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        out_dir = os.path.join(self._root, REPORTS_DIR, project_code)
        os.makedirs(out_dir, exist_ok=True)

        html_name = f"{date}_report.html"
        pdf_name = f"{date}_report.pdf"
        html_abs = os.path.join(out_dir, html_name)
        pdf_abs = os.path.join(out_dir, pdf_name)

        html_text = self._renderer.to_html(payload)
        with open(html_abs, "w", encoding="utf-8") as fh:
            fh.write(html_text)

        try:
            pdf_bytes = self._renderer.to_pdf(html_text)
        except Exception as exc:                       # noqa: BLE001
            raise PdfError(f"renderer failed for {project_code}: {exc}") from exc

        with open(pdf_abs, "wb") as fh:
            fh.write(pdf_bytes)

        kit.reports.add(
            project_code,
            f"{REPORTS_DIR}/{project_code}/{pdf_name}",
            f"{REPORTS_DIR}/{project_code}/{html_name}",
            payload.prepared_for,
            sha256_bytes(html_text.encode("utf-8")),
        )

        rows = kit.reports.list_for(project_code)
        return rows[0] if rows else None
