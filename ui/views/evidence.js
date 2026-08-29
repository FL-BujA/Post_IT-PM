/* ui/views/evidence.js — the glue view.

   Attach a file, see what is attached, and open one. The row is the truth
   of where a file lives: this view never constructs a path, it shows the
   rel_path the server stored and hands that same string back when the PM
   asks to open it.
*/

const SOURCE_TYPES = [
  "email",
  "spreadsheet",
  "drawing",
  "photo",
  "document",
  "other",
];

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function shortHash(sha) {
  return sha ? String(sha).slice(0, 12) : "—";
}

function fileName(relPath) {
  return String(relPath || "").split("/").pop();
}

function sizeLabel(bytes) {
  if (!bytes && bytes !== 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function attachForm() {
  const options = SOURCE_TYPES.map(
    (t) => `<option value="${t}">${t}</option>`
  ).join("");

  return `
    <form id="attach-form" class="card attach">
      <div class="attach-row">
        <input type="file" id="attach-file" required>
        <select id="attach-type" aria-label="Source type">${options}</select>
      </div>
      <input type="text" id="attach-note" placeholder="What is this, and why does it matter?">
      <button type="submit" class="icon-button">Attach</button>
    </form>`;
}

function renderRow(row) {
  return `
    <li class="evidence-row" data-rel="${escapeHtml(row.rel_path)}">
      <div class="evidence-main">
        <p class="evidence-name">${escapeHtml(fileName(row.rel_path))}</p>
        <p class="evidence-meta">
          <span class="chip">${escapeHtml(row.source_type)}</span>
          <span class="mono">${escapeHtml(sizeLabel(row.size))}</span>
          <span>${escapeHtml((row.attached_at || "").slice(0, 10))}</span>
        </p>
        ${row.note ? `<p class="evidence-note">${escapeHtml(row.note)}</p>` : ""}
      </div>
      <div class="evidence-side">
        <code class="sha mono" title="${escapeHtml(row.sha256)}">${escapeHtml(
    shortHash(row.sha256)
  )}</code>
        <button type="button" class="icon-button open-file">Open</button>
      </div>
    </li>`;
}

/**
 * Render the evidence view.
 *
 * onAttach(formData) posts the multipart body and resolves with the new
 * row; onOpen(relPath) calls the C4.3 intent; both reject with an Error
 * the caller reports.
 */
export function renderEvidence(host, rows, { onAttach, onOpen, onError } = {}) {
  host.className = "evidence";

  const list =
    rows.length === 0
      ? `<p class="empty">Nothing attached yet. The first file you attach
           becomes part of the project's story.</p>`
      : `<ul class="evidence-list">${rows.map(renderRow).join("")}</ul>`;

  host.innerHTML = attachForm() + list;

  const form = host.querySelector("#attach-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = host.querySelector("#attach-file").files[0];
    if (!file) return;

    const body = new FormData();
    body.append("file", file);
    body.append("source_type", host.querySelector("#attach-type").value);
    body.append("note", host.querySelector("#attach-note").value);

    try {
      await onAttach(body);
      form.reset();
    } catch (err) {
      // the input is cleared either way: a rejected file should not look
      // as though it is still queued
      form.reset();
      if (onError) onError(err);
    }
  });

  for (const button of host.querySelectorAll(".open-file")) {
    button.addEventListener("click", async () => {
      const rel = button.closest(".evidence-row").dataset.rel;
      try {
        await onOpen(rel);
      } catch (err) {
        if (onError) onError(err);
      }
    });
  }
}
