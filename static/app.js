// Email Context demo UI. Vanilla JS, no build, hash-routing.

const STORAGE = {
  access: "ea.access",
  refresh: "ea.refresh",
  me: "ea.me",
};

class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

// --- Fetch helper with auto-refresh on 401 -------------------------------
async function api(path, options = {}, _retried = false) {
  const access = localStorage.getItem(STORAGE.access);
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const res = await fetch(path, { ...options, headers });

  if (res.status === 401 && !_retried && localStorage.getItem(STORAGE.refresh)) {
    const refreshed = await tryRefresh();
    if (refreshed) return api(path, options, true);
    logout();
    throw new ApiError(401, { detail: "Session expired" });
  }

  // Try to parse JSON even on error
  let body = null;
  const text = await res.text();
  if (text) {
    try { body = JSON.parse(text); } catch { body = { detail: text }; }
  }

  if (!res.ok) {
    if (res.status === 429) {
      const retryAfter = res.headers.get("Retry-After");
      const detail = retryAfter ? `Rate limited. Try again in ${retryAfter}s.` : "Rate limited.";
      throw new ApiError(429, { detail });
    }
    throw new ApiError(res.status, body);
  }
  return body;
}

async function tryRefresh() {
  const refresh = localStorage.getItem(STORAGE.refresh);
  if (!refresh) return false;
  try {
    const res = await fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem(STORAGE.access, data.access);
    if (data.refresh) localStorage.setItem(STORAGE.refresh, data.refresh);
    return true;
  } catch {
    return false;
  }
}

// --- Auth & session ------------------------------------------------------
async function login(email, password) {
  const data = await api("/api/auth/token/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(STORAGE.access, data.access);
  localStorage.setItem(STORAGE.refresh, data.refresh);
  const me = await api("/api/auth/me/");
  localStorage.setItem(STORAGE.me, JSON.stringify(me));
  return me;
}

function logout() {
  localStorage.removeItem(STORAGE.access);
  localStorage.removeItem(STORAGE.refresh);
  localStorage.removeItem(STORAGE.me);
  window.location.hash = "#/login";
  render();
}

function currentMe() {
  const raw = localStorage.getItem(STORAGE.me);
  return raw ? JSON.parse(raw) : null;
}

// --- Polling helper ------------------------------------------------------
function pollTask(taskId, onTerminal, { intervalMs = 2000, capMs = 60_000 } = {}) {
  const started = Date.now();
  const tick = async () => {
    try {
      const s = await api(`/api/tasks/${taskId}/`);
      if (s.status === "SUCCESS" || s.status === "FAILURE" || s.status === "REVOKED") {
        onTerminal(s);
        return;
      }
      if (Date.now() - started > capMs) {
        onTerminal({ status: "TIMEOUT", error: "Still running after 60s — check the worker." });
        return;
      }
      setTimeout(tick, intervalMs);
    } catch (e) {
      onTerminal({ status: "ERROR", error: e.message });
    }
  };
  tick();
}

// --- Router --------------------------------------------------------------
const SCREENS = ["login", "thread", "reports"];
function route() {
  const hash = window.location.hash || "#/thread";
  const seg = hash.replace("#/", "").split("/")[0];
  const me = currentMe();

  if (!me && seg !== "login") {
    window.location.hash = "#/login";
    return;
  }
  if (me && seg === "login") {
    window.location.hash = "#/thread";
    return;
  }

  for (const s of SCREENS) {
    document.getElementById(`screen-${s}`).hidden = s !== seg;
  }
  if (seg === "thread") onShowThread();
  if (seg === "reports") onShowReports();
}

function render() {
  const me = currentMe();
  document.getElementById("logout-btn").hidden = !me;
  document.getElementById("me-badge").hidden = !me;
  if (me) {
    document.getElementById("me-badge").textContent = `${me.email} · ${me.role}`;
  }
  document.querySelector('[data-nav="thread"]').hidden = !me;
  document.querySelector('[data-nav="reports"]').hidden = !me || me.role === "member";
  route();
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", () => {
  bindLogin();
  bindThread();
  bindReports();
  document.getElementById("logout-btn").addEventListener("click", logout);
  render();
});

// --- Login screen --------------------------------------------------------
function bindLogin() {
  const form = document.getElementById("login-form");
  const errBox = document.getElementById("login-error");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.hidden = true;
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    try {
      await login(email, password);
      window.location.hash = "#/thread";
      render();
    } catch (err) {
      errBox.textContent = err.body?.detail || err.message;
      errBox.hidden = false;
    }
  });
}

// --- Thread screen -------------------------------------------------------
let currentThreadId = null;

function bindThread() {
  document.getElementById("thread-load").addEventListener("click", loadThread);
  document.getElementById("thread-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadThread();
  });
  document.getElementById("summary-generate").addEventListener("click", refreshSummary);
  document.getElementById("summary-refresh").addEventListener("click", refreshSummary);
}

async function onShowThread() {
  await loadSampleThreads();
}

async function loadSampleThreads() {
  const wrap = document.getElementById("sample-threads");
  const list = document.getElementById("sample-threads-list");
  try {
    const samples = await api("/api/threads/sample/");
    if (!samples.length) {
      wrap.hidden = true;
      return;
    }
    const me = currentMe();
    const crossFirm = me?.role === "superuser";
    list.innerHTML = "";
    for (const t of samples) {
      const btn = document.createElement("button");
      btn.className = "text-left text-xs bg-slate-100 hover:bg-indigo-100 hover:text-indigo-800 border border-slate-200 rounded px-2.5 py-1.5 max-w-xs truncate";
      btn.title = `${t.subject}\n${t.client_name} · ${t.firm_name}\nid: ${t.id}`;
      const subj = t.subject.length > 40 ? t.subject.slice(0, 37) + "…" : t.subject;
      btn.innerHTML = `
        <span class="font-medium">${escapeHtml(subj)}</span>
        <span class="text-slate-500"> · ${escapeHtml(t.client_name)}${crossFirm ? ` · ${escapeHtml(t.firm_name)}` : ""}</span>`;
      btn.addEventListener("click", () => {
        document.getElementById("thread-input").value = t.id;
        loadThread();
      });
      list.appendChild(btn);
    }
    wrap.hidden = false;
  } catch {
    wrap.hidden = true;
  }
}

async function loadThread() {
  const id = document.getElementById("thread-input").value.trim();
  const errBox = document.getElementById("thread-error");
  const body = document.getElementById("thread-body");
  errBox.hidden = true;
  if (!id) {
    errBox.textContent = "Enter a thread UUID.";
    errBox.hidden = false;
    return;
  }
  try {
    const thread = await api(`/api/threads/${id}/`);
    currentThreadId = id;
    renderThread(thread);
    body.hidden = false;
    await loadSummary(id);
  } catch (err) {
    body.hidden = true;
    errBox.textContent = err.status === 404
      ? "Thread not found in your firm."
      : (err.body?.detail || err.message);
    errBox.hidden = false;
  }
}

function renderThread(thread) {
  document.getElementById("thread-subject").textContent = thread.subject || "(no subject)";
  document.getElementById("thread-meta").textContent =
    `${thread.messages.length} messages · last activity ${fmtDate(thread.last_message_at)}`;
  const list = document.getElementById("thread-messages");
  list.innerHTML = "";
  for (const m of thread.messages) {
    const card = document.createElement("div");
    card.className = "border border-slate-200 rounded p-3 bg-slate-50/50";
    const to = (m.recipients?.to || []).join(", ") || "—";
    const cc = (m.recipients?.cc || []).join(", ");
    card.innerHTML = `
      <div class="flex items-baseline justify-between text-xs text-slate-500 mb-2">
        <div><span class="font-medium text-slate-700">${escapeHtml(m.sender_email)}</span> → ${escapeHtml(to)}${cc ? ` · cc: ${escapeHtml(cc)}` : ""}</div>
        <div>${fmtDate(m.sent_at)}</div>
      </div>
      <div class="msg-body text-sm text-slate-800">${escapeHtml(m.body)}</div>
    `;
    list.appendChild(card);
  }
}

async function loadSummary(threadId) {
  const empty = document.getElementById("summary-empty");
  const loaded = document.getElementById("summary-loaded");
  const status = document.getElementById("summary-status");
  status.hidden = true;
  try {
    const s = await api(`/api/threads/${threadId}/summary/`);
    renderSummary(s);
    empty.hidden = true;
    loaded.hidden = false;
  } catch (err) {
    if (err.status === 404) {
      empty.hidden = false;
      loaded.hidden = true;
    } else {
      status.textContent = err.body?.detail || err.message;
      status.className = "mt-4 text-sm text-red-600";
      status.hidden = false;
    }
  }
}

function renderSummary(s) {
  document.getElementById("summary-last-refreshed").textContent = fmtDate(s.last_refreshed_at);
  document.getElementById("summary-emails-count").textContent = s.emails_analyzed;
  document.getElementById("summary-stale").hidden = !s.is_stale;

  const actors = document.getElementById("summary-actors");
  actors.innerHTML = "";
  for (const a of s.payload.actors) {
    const li = document.createElement("li");
    const badge = a.role === "client"
      ? `<span class="text-xs bg-indigo-100 text-indigo-700 px-1.5 rounded">client</span>`
      : a.role === "accountant"
        ? `<span class="text-xs bg-emerald-100 text-emerald-700 px-1.5 rounded">accountant</span>`
        : `<span class="text-xs bg-slate-100 text-slate-600 px-1.5 rounded">${escapeHtml(a.role || "—")}</span>`;
    li.innerHTML = `
      <div class="flex items-center gap-2">
        ${badge}
        <span class="font-medium">${escapeHtml(a.name)}</span>
        ${a.email ? `<span class="text-xs text-slate-500">${escapeHtml(a.email)}</span>` : ""}
      </div>`;
    actors.appendChild(li);
  }

  const conc = document.getElementById("summary-conclusions");
  conc.innerHTML = "";
  if (!s.payload.conclusions.length) {
    conc.innerHTML = `<li class="text-slate-400 italic list-none -ml-5">none</li>`;
  } else {
    for (const c of s.payload.conclusions) {
      const li = document.createElement("li");
      li.textContent = c;
      conc.appendChild(li);
    }
  }

  const actions = document.getElementById("summary-actions");
  actions.innerHTML = "";
  if (!s.payload.action_items.length) {
    actions.innerHTML = `<li class="text-slate-400 italic">none</li>`;
  } else {
    for (const ai of s.payload.action_items) {
      const li = document.createElement("li");
      li.className = "border-l-2 border-indigo-300 pl-3";
      li.innerHTML = `
        <div>${escapeHtml(ai.description)}</div>
        <div class="text-xs text-slate-500 mt-0.5">
          ${ai.assignee ? `assignee: <span class="font-medium">${escapeHtml(ai.assignee)}</span>` : ""}
          ${ai.due_date ? ` · due <span class="font-medium">${escapeHtml(ai.due_date)}</span>` : ""}
        </div>`;
      actions.appendChild(li);
    }
  }
}

async function refreshSummary() {
  if (!currentThreadId) return;
  const status = document.getElementById("summary-status");
  const genBtn = document.getElementById("summary-generate");
  const refBtn = document.getElementById("summary-refresh");
  genBtn.disabled = true; refBtn.disabled = true;
  status.className = "mt-4 text-sm text-amber-700 flex items-center gap-2";
  status.textContent = "Refreshing summary…";
  status.hidden = false;

  try {
    const accepted = await api(`/api/threads/${currentThreadId}/summary/refresh/`, {
      method: "POST",
      body: "{}",
    });
    if (accepted.joined) {
      status.textContent = "Joining a refresh already in progress…";
    }
    pollTask(accepted.task_id, async (terminal) => {
      genBtn.disabled = false; refBtn.disabled = false;
      if (terminal.status === "SUCCESS") {
        await loadSummary(currentThreadId);
        status.className = "mt-4 text-sm text-emerald-700";
        const skipped = terminal.result && terminal.result.status === "skipped";
        status.textContent = (accepted.joined || skipped)
          ? "Another refresh just completed — showing latest."
          : "Summary refreshed.";
        setTimeout(() => { status.hidden = true; }, 3000);
      } else {
        status.className = "mt-4 text-sm text-red-600";
        status.textContent = terminal.error || `Task ended in ${terminal.status}`;
      }
    });
  } catch (err) {
    genBtn.disabled = false; refBtn.disabled = false;
    status.className = "mt-4 text-sm text-red-600";
    status.textContent = err.body?.detail || err.message;
  }
}

// --- Reports screen ------------------------------------------------------
let reportState = { scope: "firm", page: 1, since: "", until: "" };

function bindReports() {
  for (const btn of document.querySelectorAll("[data-report-tab]")) {
    btn.addEventListener("click", () => {
      reportState.scope = btn.dataset.reportTab;
      reportState.page = 1;
      updateReportTabsUI();
      fetchReport();
    });
  }
  document.getElementById("report-apply").addEventListener("click", () => {
    reportState.since = document.getElementById("report-since").value;
    reportState.until = document.getElementById("report-until").value;
    reportState.page = 1;
    fetchReport();
  });
  document.getElementById("report-clear").addEventListener("click", () => {
    document.getElementById("report-since").value = "";
    document.getElementById("report-until").value = "";
    reportState.since = ""; reportState.until = ""; reportState.page = 1;
    fetchReport();
  });
  document.getElementById("report-prev").addEventListener("click", () => {
    if (reportState.page > 1) { reportState.page -= 1; fetchReport(); }
  });
  document.getElementById("report-next").addEventListener("click", () => {
    reportState.page += 1; fetchReport();
  });
}

function updateReportTabsUI() {
  for (const btn of document.querySelectorAll("[data-report-tab]")) {
    const on = btn.dataset.reportTab === reportState.scope;
    btn.className = on
      ? "px-3 py-2 text-sm font-medium border-b-2 border-indigo-600 text-indigo-600"
      : "px-3 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-900";
  }
}

function onShowReports() {
  const me = currentMe();
  const gate = document.getElementById("report-403");
  const tableWrap = document.getElementById("report-table-wrap");
  if (!me || me.role === "member") {
    gate.hidden = false;
    tableWrap.hidden = true;
    document.getElementById("report-pager").hidden = true;
    return;
  }
  gate.hidden = true;
  tableWrap.hidden = false;
  document.querySelector('[data-report-tab="global"]').hidden = me.role !== "superuser";
  updateReportTabsUI();
  fetchReport();
}

async function fetchReport() {
  const path = reportState.scope === "firm" ? "/api/reports/firm/" : "/api/reports/global/";
  const params = new URLSearchParams();
  if (reportState.since) params.set("since", reportState.since + "T00:00:00Z");
  if (reportState.until) params.set("until", reportState.until + "T23:59:59Z");
  params.set("page", reportState.page);
  try {
    const data = await api(`${path}?${params.toString()}`);
    renderReport(data);
  } catch (err) {
    const tbody = document.getElementById("report-tbody");
    tbody.innerHTML = `<tr><td colspan="5" class="text-sm text-red-600 py-4">${escapeHtml(err.body?.detail || err.message)}</td></tr>`;
    document.getElementById("report-pager").hidden = true;
  }
}

function renderReport(data) {
  const thead = document.getElementById("report-thead");
  const tbody = document.getElementById("report-tbody");
  const cols = reportState.scope === "firm" ? 5 : 5;

  thead.innerHTML = reportState.scope === "firm"
    ? `<tr>
        <th class="text-left py-2 pr-4">Client</th>
        <th class="text-left py-2 pr-4">Email</th>
        <th class="text-right py-2 pr-4">Summaries</th>
        <th class="text-right py-2 pr-4">Emails analyzed</th>
        <th class="text-left py-2 pr-4">Last summarized</th>
      </tr>`
    : `<tr>
        <th class="text-left py-2 pr-4">Firm</th>
        <th class="text-right py-2 pr-4">Summaries</th>
        <th class="text-right py-2 pr-4">Clients</th>
        <th class="text-right py-2 pr-4">Emails analyzed</th>
        <th class="text-left py-2 pr-4">Last summarized</th>
      </tr>`;

  tbody.innerHTML = data.results.length
    ? data.results.map(r => renderRowWithSummaries(r)).join("")
    : `<tr><td colspan="${cols}" class="py-4 text-slate-400 italic">No rows.</td></tr>`;

  // Wire up the per-summary "Open" clicks.
  for (const a of tbody.querySelectorAll("[data-thread-id]")) {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const tid = a.dataset.threadId;
      window.location.hash = "#/thread";
      // Wait for screen swap, then load.
      setTimeout(() => {
        document.getElementById("thread-input").value = tid;
        loadThread();
      }, 0);
    });
  }

  const pager = document.getElementById("report-pager");
  pager.hidden = !data.next && !data.previous;
  document.getElementById("report-pager-info").textContent = `Page ${reportState.page} · ${data.count} rows total`;
  document.getElementById("report-prev").disabled = !data.previous;
  document.getElementById("report-next").disabled = !data.next;
}

function renderRowWithSummaries(r) {
  const headerRow = reportState.scope === "firm"
    ? `<tr class="bg-slate-50/60">
        <td class="py-2 pr-4 font-medium">${escapeHtml(r.client_name)}</td>
        <td class="py-2 pr-4 text-slate-500">${escapeHtml(r.client_email)}</td>
        <td class="py-2 pr-4 text-right">${r.summary_count}</td>
        <td class="py-2 pr-4 text-right">${r.total_emails_analyzed}</td>
        <td class="py-2 pr-4 text-slate-500">${r.last_summarized ? fmtDate(r.last_summarized) : "—"}</td>
      </tr>`
    : `<tr class="bg-slate-50/60">
        <td class="py-2 pr-4 font-medium">${escapeHtml(r.firm_name)}</td>
        <td class="py-2 pr-4 text-right">${r.summary_count}</td>
        <td class="py-2 pr-4 text-right">${r.client_count}</td>
        <td class="py-2 pr-4 text-right">${r.total_emails_analyzed}</td>
        <td class="py-2 pr-4 text-slate-500">${r.last_summarized ? fmtDate(r.last_summarized) : "—"}</td>
      </tr>`;

  const summaryRows = (r.summaries || []).map(s => {
    const left = reportState.scope === "firm"
      ? `<span class="font-medium text-slate-700">${escapeHtml(s.thread_subject)}</span>`
      : `<span class="font-medium text-slate-700">${escapeHtml(s.thread_subject)}</span>
         <span class="text-slate-500"> · ${escapeHtml(s.client_name)}</span>`;
    // Sub-row aligns "Emails analyzed" + "Last summarized" with the header columns.
    // Firm scope:   [subject (span 2)] [— summaries] [emails] [last]
    // Global scope: [subject (span 1)] [— summaries] [— clients] [emails] [last]
    const subjectColspan = reportState.scope === "firm" ? 2 : 1;
    const emptyMiddle = reportState.scope === "firm"
      ? `<td class="py-1.5 pr-4 text-right text-xs text-slate-500"></td>`
      : `<td class="py-1.5 pr-4 text-right text-xs text-slate-500"></td>
         <td class="py-1.5 pr-4 text-right text-xs text-slate-500"></td>`;
    return `<tr class="border-b border-slate-50">
      <td colspan="${subjectColspan}" class="py-1.5 pl-6 pr-4 text-sm">
        <a href="#/thread" data-thread-id="${escapeHtml(s.thread_id)}"
           class="text-indigo-600 hover:text-indigo-800 hover:underline">${left}</a>
      </td>
      ${emptyMiddle}
      <td class="py-1.5 pr-4 text-right text-xs text-slate-500">${s.emails_analyzed} emails</td>
      <td class="py-1.5 pr-4 text-xs text-slate-500">${fmtDate(s.last_refreshed_at)}</td>
    </tr>`;
  }).join("");

  return headerRow + summaryRows;
}

// --- Utilities -----------------------------------------------------------
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
