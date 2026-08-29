/* ui/views/engagement.js — who is engaged, and who needs a conversation.

   The counts come from the server's health_by_owner. This view does not
   aggregate: C3.4 makes that one definition on purpose, so the report
   strip and this screen can never disagree about a number.

   The four labels are frozen. They are the words the PM uses out loud, not
   the enum values.
*/

const KIND_LABELS = {
  defer: "deferred",
  extension_request: "asked for extension",
  late_start: "late start",
  reopen: "reopened",
};

const KIND_ORDER = ["defer", "extension_request", "late_start", "reopen"];

/* Two or more reopens is a pattern rather than an incident. */
const WATCH_REOPENS = 2;

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function renderOwner(health) {
  const counts = health.counts || {};
  const watch = (counts.reopen || 0) >= WATCH_REOPENS;

  const cells = KIND_ORDER.map((kind) => {
    const n = counts[kind] || 0;
    return `
      <div class="signal-cell${n ? "" : " zero"}">
        <span class="signal-count mono">${n}</span>
        <span class="signal-label">${KIND_LABELS[kind]}</span>
      </div>`;
  }).join("");

  return `
    <li class="owner-card${watch ? " watch" : ""}">
      <div class="owner-head">
        <span class="owner-name">${escapeHtml(health.owner)}</span>
        ${watch ? '<span class="badge watch-chip">watch</span>' : ""}
        <span class="owner-totals mono">
          ${health.open_total} open of ${health.total}
        </span>
      </div>
      <div class="signal-grid">${cells}</div>
    </li>`;
}

/**
 * Render the engagement view from health_by_owner output.
 */
export function renderEngagement(host, health) {
  if (!health || health.length === 0) {
    host.className = "empty";
    host.textContent =
      "No signals logged. Defers, extensions, late starts and reopens appear here as they happen.";
    return;
  }

  host.className = "engagement";
  host.innerHTML = `<ul class="owner-list">${health
    .map(renderOwner)
    .join("")}</ul>`;
}
