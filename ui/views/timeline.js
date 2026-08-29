/* ui/views/timeline.js — the story view.

   The one screen the PM drives on a share: what happened, in order, with
   the cycle it happened inside and a way into whatever it refers to.

   Server order is kept. The api returns events newest-first and this view
   groups them by day without re-sorting — one sort, on the server, so two
   people looking at the same project see the same sequence.
*/

const KIND_TONE = {
  charter: "accent",
  gate: "warning",
  evidence: "info",
  meeting: "info",
  signal: "danger",
  action_created: "success",
  action_status: "success",
  report: "accent",
};

/* A day header per calendar day, in the order the days appear. */
function groupByDay(events) {
  const days = [];
  let current = null;
  for (const event of events) {
    const day = (event.occurred_at || "").slice(0, 10);
    if (!current || current.day !== day) {
      current = { day, events: [] };
      days.push(current);
    }
    current.events.push(event);
  }
  return days;
}

function dayLabel(iso) {
  if (!iso) return "Undated";
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* An event that points at something the PM can open. */
function refLink(event) {
  if (!event.ref_table || event.ref_id === null) return "";
  const target = { evidence: "evidence", minutes: "meetings" }[event.ref_table];
  if (!target) return "";
  return `<button class="link" type="button"
            data-jump="${target}" data-ref="${event.ref_id}">open ${escapeHtml(
    event.ref_table
  )}</button>`;
}

function renderEvent(event) {
  const tone = KIND_TONE[event.kind] || "muted";
  const time = (event.occurred_at || "").slice(11, 16);
  const body = event.body
    ? `<p class="event-body">${escapeHtml(event.body)}</p>`
    : "";

  return `
    <li class="event" data-kind="${escapeHtml(event.kind)}" data-tone="${tone}">
      <span class="event-time mono">${escapeHtml(time)}</span>
      <span class="event-kind">${escapeHtml(event.kind)}</span>
      <div class="event-main">
        <p class="event-title">${escapeHtml(event.title)}</p>
        ${body}
        ${refLink(event)}
      </div>
    </li>`;
}

/**
 * Render the timeline into `host` from a snapshot.
 *
 * The snapshot carries the newest 20 events (C3.3). A fuller history would
 * need its own route; this view renders what the one query returns.
 */
export function renderTimeline(host, snapshot, { onJump } = {}) {
  const events = snapshot.events || [];

  if (events.length === 0) {
    host.className = "empty";
    host.textContent =
      "Nothing has happened yet. Create a project, attach evidence, or add an action.";
    return;
  }

  host.className = "timeline";

  const cycle = snapshot.current_cycle;
  const band = cycle
    ? `<div class="cycle-band">
         <span class="cycle-name">${escapeHtml(cycle.name)}</span>
         <span class="cycle-meta">${
           cycle.closed_at ? "closed" : "open"
         } · opened ${escapeHtml((cycle.opened_at || "").slice(0, 10))}</span>
       </div>`
    : "";

  const days = groupByDay(events)
    .map(
      (group) => `
      <section class="day">
        <h3 class="day-header">${escapeHtml(dayLabel(group.day))}</h3>
        <ul class="events">${group.events.map(renderEvent).join("")}</ul>
      </section>`
    )
    .join("");

  host.innerHTML = band + days;

  if (onJump) {
    for (const button of host.querySelectorAll("[data-jump]")) {
      button.addEventListener("click", () =>
        onJump(button.dataset.jump, button.dataset.ref)
      );
    }
  }
}
