/* ui/views/board.js — the priorities board.

   Three columns, the actions in each, and drag to move one between them.

   Server truth wins. A drag fires a PATCH and the card only stays where it
   was dropped if the server accepts; an illegal transition rolls it back
   and says why. An optimistic stick would let the board show a state the
   database never had, which is the one thing this tool exists to prevent.
*/

const COLUMNS = [
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In progress" },
  { key: "done", label: "Done" },
];

/* Statuses that exist but are not columns. They appear nowhere on the
   board; the timeline still carries their history. */
const OFF_BOARD = ["deferred", "cancelled"];

const CRITICAL_PRIORITY = 3;

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function renderCard(action) {
  const critical = action.priority <= CRITICAL_PRIORITY;
  const reopened =
    action.reopen_count > 0
      ? `<span class="badge reopen" title="reopened">${action.reopen_count}×</span>`
      : "";
  const due = action.due_end
    ? `<span class="due mono">${escapeHtml(action.due_end)}</span>`
    : "";

  return `
    <li class="action-card" draggable="true" data-id="${action.id}"
        data-status="${escapeHtml(action.status)}">
      <div class="action-head">
        <span class="badge priority ${critical ? "critical" : "normal"}">P${
    action.priority
  }</span>
        ${reopened}
        ${due}
      </div>
      <p class="action-title">${escapeHtml(action.title)}</p>
      <span class="owner-chip">${escapeHtml(action.owner)}</span>
    </li>`;
}

function renderColumn(column, actions) {
  const cards = actions.map(renderCard).join("");
  const body = cards || `<li class="empty-column">Nothing here</li>`;
  return `
    <section class="column" data-status="${column.key}">
      <h3 class="column-head">
        ${column.label}
        <span class="count mono">${actions.length}</span>
      </h3>
      <ul class="column-body">${body}</ul>
    </section>`;
}

/**
 * Render the board into `host`.
 *
 * onMove(id, status) must return a promise: resolved if the server took
 * the change, rejected with an Error if it refused. The card is rolled
 * back on rejection.
 */
export function renderBoard(host, snapshot, { onMove, onError } = {}) {
  const actions = snapshot.actions || [];

  if (actions.length === 0) {
    host.className = "empty";
    host.textContent = "No actions yet. Add one to start the loop.";
    return;
  }

  host.className = "board";

  // Insertion order within a column is the PM's arrangement — the server
  // already sorted, so the view groups without re-sorting.
  const byStatus = new Map(COLUMNS.map((c) => [c.key, []]));
  for (const action of actions) {
    const bucket = byStatus.get(action.status);
    if (bucket) bucket.push(action);
  }

  const offBoard = actions.filter((a) => OFF_BOARD.includes(a.status)).length;
  const note = offBoard
    ? `<p class="board-note">${offBoard} deferred or cancelled — see the timeline.</p>`
    : "";

  host.innerHTML =
    COLUMNS.map((c) => renderColumn(c, byStatus.get(c.key))).join("") + note;

  wireDrag(host, { onMove, onError });
}

function wireDrag(host, { onMove, onError }) {
  let dragged = null;
  let origin = null;

  for (const card of host.querySelectorAll(".action-card")) {
    card.addEventListener("dragstart", () => {
      dragged = card;
      origin = card.closest(".column");
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
    });
  }

  for (const column of host.querySelectorAll(".column")) {
    column.addEventListener("dragover", (event) => {
      event.preventDefault();                 // permits the drop
      column.classList.add("drop-target");
    });
    column.addEventListener("dragleave", () => {
      column.classList.remove("drop-target");
    });

    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("drop-target");
      if (!dragged || column === origin) return;

      const status = column.dataset.status;
      const body = column.querySelector(".column-body");
      const emptyRow = body.querySelector(".empty-column");
      if (emptyRow) emptyRow.remove();
      body.appendChild(dragged);

      if (!onMove) return;

      try {
        await onMove(dragged.dataset.id, status);
        dragged.dataset.status = status;
      } catch (err) {
        // the server refused: put it back where it came from
        origin.querySelector(".column-body").appendChild(dragged);
        if (onError) onError(err);
      }
    });
  }

  // a drop outside any column returns the card and fires nothing
  host.addEventListener("dragend", () => {
    if (dragged && !dragged.closest(".column")) {
      origin.querySelector(".column-body").appendChild(dragged);
    }
    dragged = null;
    origin = null;
  });
}
