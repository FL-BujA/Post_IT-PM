/* ui/views/meetings.js — minutes.

   minutes_text is rendered as plain text. Typing **bold** shows the
   asterisks, and that is correct: the minutes are a record of what was
   said, and a record that quietly reinterprets its own characters is not a
   record. No markdown parser exists in this application (C3.3 frozen).

   agreed_actions is free text too. Actions are added deliberately on the
   board, never parsed out of a paragraph.
*/

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function addForm() {
  return `
    <form id="minutes-form" class="card minutes-form">
      <div class="form-row">
        <input type="date" id="m-held" value="${today()}" required
               aria-label="Date held">
        <input type="text" id="m-attendees" placeholder="Attendees"
               aria-label="Attendees">
      </div>
      <textarea id="m-text" rows="4" required
        placeholder="What was said. Plain text — asterisks stay asterisks."
        aria-label="Minutes"></textarea>
      <div class="form-row">
        <input type="text" id="m-decisions" placeholder="Decisions"
               aria-label="Decisions">
        <input type="text" id="m-actions" placeholder="Agreed actions (free text)"
               aria-label="Agreed actions">
        <input type="text" id="m-risks" placeholder="Risks" aria-label="Risks">
      </div>
      <button type="submit" class="icon-button">Record minutes</button>
    </form>`;
}

function field(label, value) {
  if (!value) return "";
  return `<p class="m-field"><span class="m-label">${label}</span>
            ${escapeHtml(value)}</p>`;
}

function renderMinutes(row) {
  return `
    <li class="minutes-row">
      <div class="minutes-head">
        <span class="m-date mono">${escapeHtml((row.held_at || "").slice(0, 10))}</span>
        ${
          row.attendees
            ? `<span class="m-attendees">${escapeHtml(row.attendees)}</span>`
            : ""
        }
      </div>
      <pre class="minutes-text">${escapeHtml(row.minutes_text)}</pre>
      ${field("Decisions", row.decisions)}
      ${field("Agreed", row.agreed_actions)}
      ${field("Risks", row.risks)}
    </li>`;
}

/**
 * Render the meetings view. onAdd(body) posts and resolves on success.
 */
export function renderMeetings(host, rows, { onAdd, onError } = {}) {
  host.className = "meetings";

  const list =
    rows.length === 0
      ? `<p class="empty">No minutes yet. Record a meeting and it joins the
           project's timeline.</p>`
      : `<ul class="minutes-list">${rows.map(renderMinutes).join("")}</ul>`;

  host.innerHTML = addForm() + list;

  const form = host.querySelector("#minutes-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = {
      held_at: host.querySelector("#m-held").value,
      attendees: host.querySelector("#m-attendees").value || null,
      decisions: host.querySelector("#m-decisions").value || null,
      agreed_actions: host.querySelector("#m-actions").value || null,
      risks: host.querySelector("#m-risks").value || null,
      minutes_text: host.querySelector("#m-text").value,
      cycle_id: null,
    };
    try {
      await onAdd(body);
      form.reset();
      host.querySelector("#m-held").value = today();
    } catch (err) {
      if (onError) onError(err);
    }
  });
}
