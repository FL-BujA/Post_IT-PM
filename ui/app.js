import { renderMeetings } from "/static/views/meetings.js";
import { renderEngagement } from "/static/views/engagement.js";
import { renderEvidence } from "/static/views/evidence.js";
import { renderBoard } from "/static/views/board.js";
import { renderTimeline } from "/static/views/timeline.js";
/* ui/app.js — the shell: view switching, the project switcher, the theme,
   and the one piece of client state the app is allowed to keep.

   PRISM 6: folders remember where you left things. That is the whole of the
   client state here — the selected project and the theme, under a single
   key. Nothing else is cached: server data is read on demand, so the ui can
   never show something the database does not.
*/

const STATE_KEY = "pmckit.state";   // the ONLY key this app writes
const API = "/api";

const state = {
  project: null,
  theme: "dark",
  view: "timeline",
};

/* ---- persistence ------------------------------------------------------ */

function load() {
  try {
    Object.assign(state, JSON.parse(localStorage.getItem(STATE_KEY) || "{}"));
  } catch {
    /* a corrupt value is not worth a crash; defaults stand */
  }
}

function save() {
  localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

/* ---- feedback (PRISM 5.5: toasts for background results only) --------- */

function toast(message, kind = "ok") {
  const host = document.getElementById("toasts");
  while (host.children.length >= 3) host.removeChild(host.firstChild);

  const el = document.createElement("div");
  el.className = "toast";
  el.dataset.kind = kind;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

/* ---- api -------------------------------------------------------------- */

async function api(path, options) {
  const res = await fetch(API + path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = body.error || { code: "http", message: res.statusText };
    throw new Error(`${err.code}: ${err.message}`);
  }
  return body;
}

/* ---- theme ------------------------------------------------------------ */

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  document.getElementById("theme-toggle").textContent =
    state.theme === "dark" ? "Light" : "Dark";
}

function toggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  applyTheme();
  save();
}

/* ---- views ------------------------------------------------------------ */

function showView(name) {
  state.view = name;
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.id !== `view-${name}`;
  }
  for (const button of document.querySelectorAll(".nav button")) {
    if (button.dataset.view === name) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  }
  save();
  render();
}

/* ---- projects --------------------------------------------------------- */

async function loadProjects() {
  const select = document.getElementById("project-switcher");
  try {
    const { projects } = await api("/projects");
    select.innerHTML = "";

    if (projects.length === 0) {
      select.innerHTML = '<option value="">No projects yet</option>';
      return;
    }

    for (const p of projects) {
      const option = document.createElement("option");
      option.value = p.code;
      option.textContent = `${p.code} — ${p.name}`;
      select.appendChild(option);
    }

    // the remembered project, if it still exists
    const known = projects.some((p) => p.code === state.project);
    state.project = known ? state.project : projects[0].code;
    select.value = state.project;
    save();
    render();
  } catch (err) {
    select.innerHTML = '<option value="">Unavailable</option>';
    toast(String(err.message), "error");
  }
}

/* ---- render ----------------------------------------------------------- */

async function render() {
  if (!state.project) return;

  let snapshot;
  try {
    ({ snapshot } = await api(`/projects/${state.project}`));
  } catch (err) {
    toast(String(err.message), "error");
    return;
  }

  const counts = {
    timeline: snapshot.events.length,
    board: snapshot.actions.length,
    meetings: snapshot.minutes.length,
    evidence: 0,
    report: 0,
    engagement: snapshot.signals.length,
  };

  // The views themselves arrive in their own cards; the shell only proves
  // the data reaches them.
  const body = document.getElementById(`${state.view}-body`);
  if (!body) return;

  if (state.view === "timeline") {
    renderTimeline(body, snapshot, { onJump: (v) => showView(v) });
    return;
  }
  if (state.view === "board") {
    renderBoard(body, snapshot, {
      onMove: (id, status) => api(`/projects/${state.project}/actions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) }),
      onError: (e) => toast(String(e.message), "error"),
    });
    return;
  }
  if (state.view === "meetings") {
    const { minutes } = await api(`/projects/${state.project}/minutes`);
    renderMeetings(body, minutes, {
      onAdd: (b) => api(`/projects/${state.project}/minutes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(() => render()),
      onError: (e) => toast(String(e.message), "error"),
    });
    return;
  }
  if (state.view === "engagement") {
    const { health } = await api(`/projects/${state.project}/engagement/health`);
    renderEngagement(body, health);
    return;
  }
  const n = counts[state.view];
  if (n === 0) return;                       // keep the view's empty copy

  body.classList.remove("empty");
  body.innerHTML = `<div class="card">${n} item${n === 1 ? "" : "s"} — the ${
    state.view
  } view renders these in its own card.</div>`;
}

/* ---- search ----------------------------------------------------------- */

let searchTimer = null;

function onSearch(event) {
  clearTimeout(searchTimer);
  const terms = event.target.value.trim();
  if (terms.length < 2) return;

  // one request per pause, never on an interval
  searchTimer = setTimeout(async () => {
    try {
      const { hits } = await api(
        `/search?terms=${encodeURIComponent(terms)}&project=${state.project || ""}`
      );
      toast(`${hits.length} hit${hits.length === 1 ? "" : "s"} for “${terms}”`);
    } catch (err) {
      toast(String(err.message), "error");
    }
  }, 250);
}

/* ---- wiring ----------------------------------------------------------- */

function init() {
  load();
  applyTheme();
  showView(state.view);

  document
    .getElementById("theme-toggle")
    .addEventListener("click", toggleTheme);

  for (const button of document.querySelectorAll(".nav button")) {
    button.addEventListener("click", () => showView(button.dataset.view));
  }

  document
    .getElementById("project-switcher")
    .addEventListener("change", (e) => {
      state.project = e.target.value;
      save();
      render();
    });

  document.getElementById("search").addEventListener("input", onSearch);

  loadProjects();
}

document.addEventListener("DOMContentLoaded", init);
