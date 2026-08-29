/* ui/views/report.js — generate a status report and find the old ones.

   The html file is the source of record (C3.5): the pdf is what gets sent,
   but the html is what the sha256 in report_history covers. Both are
   listed, and either opens through the same C4.3 intent the evidence view
   uses — this view never constructs a path.

   Prepared for defaults to the project's sponsor. Left blank, the page
   renders an em dash rather than a name nobody agreed to.
*/

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function generateForm(sponsor) {
  const hint = sponsor
    ? `defaults to ${escapeHtml(sponsor)}`
    : "no sponsor set — the page will show an em dash";

  return `
    <form id="report-form" class="card report-form">
      <div class="form-row">
        <input type="text" id="r-prepared" placeholder="Prepared for"
               aria-label="Prepared for">
        <button type="submit" class="icon-button">Generate report</button>
      </div>
      <p class="hint">${hint}</p>
    </form>`;
}

function renderReport(row) {
  return `
    <li class="report-row">
      <div class="report-main">
        <p class="report-when mono">${escapeHtml(
          (row.generated_at || "").slice(0, 16).replace("T", " ")
        )}</p>
        <p class="report-for">for ${escapeHtml(row.prepared_for || "—")}</p>
        <code class="sha mono" title="sha256 of the html source of record"
          >${escapeHtml(String(row.snapshot_sha256 || "").slice(0, 12))}</code>
      </div>
      <div class="report-side">
        <button type="button" class="icon-button open-report"
                data-rel="${escapeHtml(row.html_rel_path)}">HTML</button>
        <button type="button" class="icon-button open-report"
                data-rel="${escapeHtml(row.pdf_rel_path)}">PDF</button>
      </div>
    </li>`;
}

/**
 * Render the report view.
 *
 * onGenerate(preparedFor) posts and resolves when the report exists;
 * onOpen(relPath) calls the C4.3 intent.
 */
export function renderReport(
  host,
  reports,
  { sponsor, onGenerate, onOpen, onError } = {}
) {
  host.className = "reports";

  const list =
    reports.length === 0
      ? `<p class="empty">No reports yet. One call builds the page from
           whatever the project looks like right now.</p>`
      : `<ul class="report-list">${reports.map(renderReport).join("")}</ul>`;

  host.innerHTML = generateForm(sponsor) + list;

  const form = host.querySelector("#report-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const preparedFor = host.querySelector("#r-prepared").value.trim() || null;
    const button = form.querySelector("button");
    button.disabled = true;
    button.textContent = "Generating…";
    try {
      await onGenerate(preparedFor);
    } catch (err) {
      if (onError) onError(err);
    } finally {
      button.disabled = false;
      button.textContent = "Generate report";
    }
  });

  for (const button of host.querySelectorAll(".open-report")) {
    button.addEventListener("click", async () => {
      try {
        await onOpen(button.dataset.rel);
      } catch (err) {
        if (onError) onError(err);
      }
    });
  }
}
