const state = {
  snapshot: null,
  timer: null,
};

const ATTENTION_MARKERS = [
  "Needs decision:",
  "Needs approval:",
  "Blocked:",
  "Verification failed:",
  "Contract drift:",
  "Ownership violation:",
  "Missing Linear:",
];

const ACTIVE_STATUSES = new Set([
  "running",
  "report-ready",
  "verification-failed",
  "blocked",
  "waiting",
  "assigned",
]);

const DONE_STATUSES = new Set([
  "ready-for-integration",
  "merged",
  "cancelled",
  "completed",
]);

const STALE_THRESHOLD_SEC = 900;

function isLiveSession(session) {
  if (!session || !ACTIVE_STATUSES.has(session.status)) return false;
  if (session.runtime_status === "exited" || session.runtime_status === "missing") {
    return false;
  }
  const ts = session.last_activity ? new Date(session.last_activity).getTime() : 0;
  if (!ts) return false;
  return (Date.now() - ts) / 1000 <= STALE_THRESHOLD_SEC;
}

function formatRelative(value) {
  if (!value) return "no time";
  const ts = new Date(value);
  if (Number.isNaN(ts.getTime())) return value;
  const diffMs = Date.now() - ts.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 30) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.round(hr / 24);
  return `${days}d ago`;
}

function shortTime(value) {
  if (!value) return "--:--";
  const ts = new Date(value);
  if (Number.isNaN(ts.getTime())) return value;
  return ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function statusKind(session) {
  if (session.needs_human) return "attention";
  if (DONE_STATUSES.has(session.status)) return "done";
  if (ACTIVE_STATUSES.has(session.status)) {
    if (session.status === "blocked" || session.status === "verification-failed") {
      return "danger";
    }
    return "active";
  }
  return "done";
}

function groupSessionsByLinear(sessions) {
  const grouped = new Map();
  for (const session of sessions) {
    const key = session.linear_issue_id || "no-linear";
    if (!grouped.has(key)) {
      grouped.set(key, {
        linear_issue_id: session.linear_issue_id,
        linear_issue_url: session.linear_issue_url,
        linear_title: session.linear_title,
        linear_status: session.linear_status,
        sessions: [],
      });
    }
    grouped.get(key).sessions.push(session);
  }
  return [...grouped.values()];
}

function renderActiveWork(snapshot) {
  const allSessions = (snapshot.mission.runtime && snapshot.mission.runtime.sessions) || [];
  const sessions = allSessions.filter(isLiveSession);
  const container = byId("mcActive");
  const countEl = byId("mcActiveCount");

  if (!sessions.length) {
    container.innerHTML = `<div class="mc-empty">No live agent sessions. Active work appears here only while a worker has a fresh heartbeat.</div>`;
    countEl.textContent = "0 issues";
    return;
  }

  const groups = groupSessionsByLinear(sessions);
  countEl.textContent = `${groups.length} issue${groups.length === 1 ? "" : "s"}`;

  container.innerHTML = groups
    .map((group) => {
      const linearLabel = group.linear_issue_url
        ? `<a href="${escapeHtml(group.linear_issue_url)}" target="_blank" rel="noreferrer">${escapeHtml(group.linear_issue_id || "no-linear")}</a>`
        : `<strong>${escapeHtml(group.linear_issue_id || "no-linear")}</strong>`;
      const title = group.linear_title ? `<span class="mc-issue-title">${escapeHtml(group.linear_title)}</span>` : "";
      const status = group.linear_status ? `<span class="mc-issue-meta">${escapeHtml(group.linear_status)}</span>` : "";
      const sortedSessions = [...group.sessions].sort((a, b) => {
        const ta = new Date(a.last_activity || 0).getTime();
        const tb = new Date(b.last_activity || 0).getTime();
        return tb - ta;
      });
      const rows = sortedSessions
        .map((session) => {
          const kind = statusKind(session);
          const role = `${session.role || "?"}/${session.agent || "?"}`;
          return `
            <li class="mc-session">
              <span class="mc-dot ${kind}"></span>
              <span class="mc-session-role">${escapeHtml(role)}</span>
              <span class="mc-session-status">${escapeHtml(session.status || "unknown")}</span>
              <span class="mc-session-when" title="${escapeHtml(session.last_activity || "")}">${escapeHtml(formatRelative(session.last_activity))}</span>
            </li>
          `;
        })
        .join("");
      return `
        <article class="mc-issue">
          <div class="mc-issue-head">
            ${linearLabel}
            ${title}
            ${status}
          </div>
          <ul class="mc-sessions">${rows}</ul>
        </article>
      `;
    })
    .join("");
}

function renderNeedsAttention(snapshot) {
  const container = byId("mcAttention");
  const countEl = byId("mcAttentionCount");
  const items = [];

  // Sessions explicitly flagged for human attention.
  const sessions = (snapshot.mission.runtime && snapshot.mission.runtime.sessions) || [];
  for (const session of sessions) {
    if (session.needs_human) {
      items.push({
        icon: "👤",
        title: `${session.role || "?"}/${session.agent || "?"} — ${session.task_id || "no task"}`,
        body: session.current_note || "Session flagged needs_human=true",
      });
    }
    if (session.status === "blocked" || session.status === "verification-failed") {
      items.push({
        icon: "⛔",
        title: `${session.task_id || "no task"} — ${session.status}`,
        body: session.current_note || "Session is blocked",
      });
    }
  }

  // Decision-log lines that carry attention markers.
  for (const dec of snapshot.decisions || []) {
    const text = dec.text || "";
    const marker = ATTENTION_MARKERS.find((m) => text.includes(m));
    if (!marker) continue;
    items.push({
      icon: "⚠",
      title: marker,
      body: text.replace(/^[-*]\s*/, ""),
      source: `${dec.source}:${dec.line}`,
    });
  }

  // Proposed handoffs awaiting acceptance.
  for (const h of snapshot.handoffs || []) {
    if (h.status === "proposed") {
      items.push({
        icon: "🤝",
        title: `Handoff proposed: ${h.from_role || "?"} → ${h.to_role || "?"}`,
        body: h.reason || "Awaiting acceptance",
      });
    }
  }

  const process = snapshot.process_control || {};
  if (process.requires_orchestrator || process.gate === "attention" || process.gate === "blocked") {
    items.push({
      icon: "⚠",
      title: `Process control: ${process.gate || "attention"}`,
      body: process.summary || "Changed files need orchestration review.",
      source: "git status / ownership.yaml / runtime.json",
    });
  }

  countEl.textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;

  if (!items.length) {
    container.innerHTML = `<div class="mc-empty">Nothing flagged. All clear.</div>`;
    return;
  }

  container.innerHTML = items
    .map(
      (item) => `
        <div class="mc-attention-item">
          <span class="mc-attention-icon">${item.icon}</span>
          <div class="mc-attention-body">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.body)}</span>
            ${item.source ? `<span style="opacity:0.7">${escapeHtml(item.source)}</span>` : ""}
          </div>
        </div>
      `,
    )
    .join("");
}

function renderRepoActivity(live) {
  const container = byId("mcRepo");
  const countEl = byId("mcRepoCount");

  if (!live) {
    container.innerHTML = `<div class="mc-empty">Repo activity not loaded yet.</div>`;
    countEl.textContent = "no data";
    return;
  }
  const commits = live.commits || [];
  const prs = live.pull_requests || [];
  const errors = live.errors || [];

  countEl.textContent = `${commits.length} commit${commits.length === 1 ? "" : "s"} · ${prs.length} PR${prs.length === 1 ? "" : "s"}`;

  const errorBanner = errors.length
    ? `<div class="mc-empty" style="color:#f37070">⚠ ${escapeHtml(errors.join(" · "))}</div>`
    : "";

  const prRows = prs.length
    ? prs
        .map((pr) => {
          const rollup = pr.checks_rollup || "none";
          const dotClass = rollup === "fail" ? "danger" : rollup === "pending" ? "attention" : rollup === "pass" ? "active" : "done";
          const draftTag = pr.isDraft ? '<span style="color:var(--muted,#8d93b3);font-size:0.75rem;">[draft]</span> ' : "";
          return `
            <div class="mc-pr-row">
              <span class="mc-dot ${dotClass}" title="checks: ${escapeHtml(rollup)}"></span>
              <span class="mc-pr-num"><a href="${escapeHtml(pr.url || "#")}" target="_blank" rel="noreferrer">#${escapeHtml(pr.number)}</a></span>
              <span class="mc-pr-title">${draftTag}${escapeHtml(pr.title)} <span class="mc-pr-branch">${escapeHtml(pr.headRefName)}</span></span>
              <span class="mc-pr-when" title="${escapeHtml(pr.updatedAt || "")}">${escapeHtml(formatRelative(pr.updatedAt))}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="mc-empty">No open PRs.</div>`;

  const commitRows = commits.length
    ? commits
        .map((c) => {
          const subj = c.subject || "";
          const refs = c.refs ? `<span class="meta">${escapeHtml(c.refs)}</span>` : "";
          return `
            <div class="mc-repo-row">
              <span class="when" title="${escapeHtml(c.committed_at || "")}">${escapeHtml(formatRelative(c.committed_at))}</span>
              <code>${escapeHtml(c.short)}</code>
              <span class="subject" title="${escapeHtml(subj)}">${escapeHtml(subj)} <span class="meta">${escapeHtml(c.author)}</span> ${refs}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="mc-empty">No commits in the last 24h.</div>`;

  container.innerHTML = `
    ${errorBanner}
    <div class="mc-repo-section">
      <h4>Open pull requests</h4>
      ${prRows}
    </div>
    <div class="mc-repo-section">
      <h4>Recent commits (24h)</h4>
      ${commitRows}
    </div>
  `;
}

function renderRecentActivity(snapshot) {
  const container = byId("mcActivity");
  // Use structured handoffs only (those with from_role + to_role).
  const handoffs = (snapshot.handoffs || []).filter((h) => h.from_role && h.to_role);
  // Sort newest first by created_at.
  handoffs.sort((a, b) => {
    const ta = new Date(a.created_at || 0).getTime();
    const tb = new Date(b.created_at || 0).getTime();
    return tb - ta;
  });
  const top = handoffs.slice(0, 5);

  if (!top.length) {
    container.innerHTML = `<div class="mc-empty">No structured handoffs recorded yet.</div>`;
    return;
  }

  container.innerHTML = top
    .map((h) => {
      const when = shortTime(h.created_at);
      const path = `<code>${escapeHtml(h.from_role)} → ${escapeHtml(h.to_role)}</code>`;
      const ctx = [h.linear_issue_id, h.task_id].filter(Boolean).join(" ");
      return `
        <div class="mc-activity-row">
          <span class="when" title="${escapeHtml(h.created_at || "")}">${escapeHtml(when)}</span>
          <span>${path} <span style="opacity:0.7">${escapeHtml(ctx)}</span></span>
        </div>
      `;
    })
    .join("");
}

function statusClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("fail") || text.includes("blocked") || text.includes("missing")) return "danger";
  if (text.includes("done") || text.includes("complete") || text.includes("pass")) return "done";
  if (text.includes("running") || text.includes("progress") || text.includes("active")) return "active";
  if (text.includes("ready") || text.includes("planned") || text.includes("waiting")) return "attention";
  return "neutral";
}

function renderMarkdownCell(value) {
  const text = String(value || "");
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  let output = "";
  let lastIndex = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    output += escapeHtml(text.slice(lastIndex, match.index));
    output += `<a href="${escapeHtml(match[2])}" target="_blank" rel="noreferrer">${escapeHtml(match[1])}</a>`;
    lastIndex = pattern.lastIndex;
  }
  output += escapeHtml(text.slice(lastIndex));
  return output;
}

function localizedTaskLabel(value, labels) {
  const text = String(value || "");
  const direct = labels && labels[text];
  if (direct) return direct;
  const match = text.match(/ENG-\d+|MISSION-OPEN/);
  if (match && labels && labels[match[0]]) return `${match[0]} — ${labels[match[0]]}`;
  return "";
}

function renderPlanChecklist(snapshot) {
  const container = byId("mcPlan");
  const countEl = byId("mcPlanCount");
  const plan = (snapshot.mission && snapshot.mission.plan_checklist) || {};
  const items = plan.items || [];
  const total = plan.total || 0;
  const done = plan.done || 0;
  const open = plan.open || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;

  const localeNote = plan.locale && plan.locale.exists ? ` · ${plan.locale.locale}` : "";
  countEl.textContent = total ? `${done}/${total} done · ${open} open${localeNote}` : "missing checklist";

  if (!plan.exists) {
    container.innerHTML = `
      <div class="mc-empty">
        No <code>PLAN_CHECKLIST.md</code> is present for this mission. This is the process gap to close before the next large wave.
      </div>
    `;
    return;
  }

  const openItems = items.filter((item) => !item.done).slice(0, 10);
  const doneItems = items.filter((item) => item.done).slice(-5).reverse();
  const openHtml = openItems.length
    ? openItems.map((item) => `<li><span class="mc-box open"></span><span>${escapeHtml(item.display_text || item.text)}</span><small>${escapeHtml(item.display_section || item.section)}:${item.line}</small></li>`).join("")
    : `<li><span class="mc-box done"></span><span>All checklist items are marked complete.</span></li>`;
  const doneHtml = doneItems.length
    ? doneItems.map((item) => `<li><span class="mc-box done"></span><span>${escapeHtml(item.display_text || item.text)}</span><small>${escapeHtml(item.display_section || item.section)}:${item.line}</small></li>`).join("")
    : "";

  container.innerHTML = `
    <div class="mc-progress">
      <div class="mc-progress-bar"><span style="width:${pct}%"></span></div>
      <strong>${pct}%</strong>
      <code>${escapeHtml(plan.path || "")}</code>
    </div>
    <div class="mc-check-columns">
      <div>
        <h4>Open</h4>
        <ul class="mc-check-list">${openHtml}</ul>
      </div>
      <div>
        <h4>Recently done</h4>
        <ul class="mc-check-list">${doneHtml || '<li><span class="mc-box neutral"></span><span>No completed checklist items yet.</span></li>'}</ul>
      </div>
    </div>
  `;
}

function renderWorkflow(snapshot) {
  const container = byId("mcWorkflow");
  const countEl = byId("mcWorkflowCount");
  const workflow = (snapshot.mission && snapshot.mission.workflow) || {};
  const plan = (snapshot.mission && snapshot.mission.plan_checklist) || {};
  const boardRows = workflow.board_rows || [];
  const dagSections = plan.dag_sections || [];
  const taskLabels = workflow.task_labels || plan.task_labels || {};
  countEl.textContent = `${boardRows.length} board rows · ${dagSections.length} DAG sections`;

  const dagHtml = dagSections.length
    ? dagSections.map((section) => `
        <article class="mc-dag-section">
          <h4>${escapeHtml(section.display_title || section.title)}</h4>
          <pre>${escapeHtml(section.body || "No DAG body recorded.")}</pre>
        </article>
      `).join("")
    : `<div class="mc-empty">No DAG or wave section found in <code>PLAN_CHECKLIST.md</code>. The board below is the current fallback workflow source.</div>`;

  const boardHtml = boardRows.length
    ? `
      <div class="mc-table-wrap">
        <table class="mc-table">
          <thead><tr>${Object.keys(boardRows[0]).map((key) => `<th>${escapeHtml(key)}</th>`).join("")}</tr></thead>
          <tbody>
            ${boardRows.slice(0, 12).map((row) => `
              <tr>
                ${Object.entries(row).map(([key, value]) => {
                  if (key.toLowerCase().includes("status")) {
                    return `<td><span class="mc-status ${statusClass(value)}">${escapeHtml(value)}</span></td>`;
                  }
                  if (key.toLowerCase() === "task") {
                    const translated = localizedTaskLabel(value, taskLabels);
                    return `<td>${translated ? escapeHtml(translated) : renderMarkdownCell(value)}</td>`;
                  }
                  return `<td>${renderMarkdownCell(value)}</td>`;
                }).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `
    : `<div class="mc-empty">No board rows found.</div>`;

  container.innerHTML = `
    ${dagHtml}
    <h4 class="mc-subhead">Board</h4>
    ${boardHtml}
  `;
}

function renderWorkers(snapshot) {
  const container = byId("mcWorkers");
  const countEl = byId("mcWorkersCount");
  const workflow = (snapshot.mission && snapshot.mission.workflow) || {};
  const workers = workflow.workers || [];
  const counts = workflow.status_counts || {};
  const taskLabels = workflow.task_labels || {};
  const countText = Object.entries(counts).map(([key, value]) => `${key}: ${value}`).join(" · ");
  countEl.textContent = workers.length ? `${workers.length} workers · ${countText}` : "0 workers";

  if (!workers.length) {
    container.innerHTML = `<div class="mc-empty">No workers are recorded in runtime.json.</div>`;
    return;
  }

  container.innerHTML = workers.map((worker) => {
    const linear = worker.linear_issue_url
      ? `<a href="${escapeHtml(worker.linear_issue_url)}" target="_blank" rel="noreferrer">${escapeHtml(worker.linear_issue_id || "Linear")}</a>`
      : `<span class="bad">${escapeHtml(worker.linear_issue_id || "Missing Linear")}</span>`;
    return `
      <article class="mc-worker-card">
        <div class="mc-worker-head">
          <span class="mc-dot ${statusClass(worker.status)}"></span>
          <strong>${escapeHtml(localizedTaskLabel(worker.task_id, taskLabels) || worker.task_id || "No task")}</strong>
          <span class="mc-status ${statusClass(worker.status)}">${escapeHtml(worker.status || "unknown")}</span>
        </div>
        <dl>
          <div><dt>Linear</dt><dd>${linear}</dd></div>
          <div><dt>Role</dt><dd>${escapeHtml(worker.role || "Not set")} / ${escapeHtml(worker.agent || "Not set")}</dd></div>
          <div><dt>Phase</dt><dd>${escapeHtml(worker.phase || "Not set")}</dd></div>
          <div><dt>Branch</dt><dd>${escapeHtml(worker.branch || "Not set")}</dd></div>
          <div><dt>Worktree</dt><dd>${escapeHtml(worker.worktree || "Not set")}</dd></div>
          <div><dt>Activity</dt><dd>${escapeHtml(worker.runtime_status || "unknown")} · ${escapeHtml(worker.agent_activity || "unknown")} · ${escapeHtml(formatRelative(worker.last_activity))}</dd></div>
          <div class="wide"><dt>Note</dt><dd>${escapeHtml(worker.current_note || "No note")}</dd></div>
        </dl>
      </article>
    `;
  }).join("");
}

function renderVerificationGate(snapshot) {
  const container = byId("mcVerify");
  const countEl = byId("mcVerifyCount");
  const verification = (snapshot.mission && snapshot.mission.verification_control) || {};
  const signals = verification.signals || [];
  const risks = snapshot.git_risks || [];
  const failCount = signals.filter((item) => item.result === "fail").length;
  const passCount = signals.filter((item) => item.result === "pass").length;
  countEl.textContent = `${passCount} pass signals · ${failCount} fail signals · ${risks.length} risks`;

  const risksHtml = risks.length
    ? risks.map((risk) => `
        <div class="mc-risk ${escapeHtml(risk.level || "warning")}">
          <strong>${escapeHtml(risk.title)}</strong>
          <span>${escapeHtml(risk.detail)}</span>
        </div>
      `).join("")
    : `<div class="mc-risk good"><strong>No git/process risks detected</strong><span>Dashboard did not find dirty-tree, branch sync, or mission-closure drift risks.</span></div>`;

  const signalHtml = signals.length
    ? signals.slice(-14).reverse().map((signal) => `
        <div class="mc-verify-row">
          <span class="mc-status ${statusClass(signal.result)}">${escapeHtml(signal.result)}</span>
          <span>${escapeHtml(signal.text)}</span>
          <small>${escapeHtml(signal.source)}:${escapeHtml(signal.line)}</small>
        </div>
      `).join("")
    : `<div class="mc-empty">No verification evidence found in verification/closure/incidents files.</div>`;

  container.innerHTML = `
    <div class="mc-risk-list">${risksHtml}</div>
    <h4 class="mc-subhead">Evidence</h4>
    <div class="mc-verify-list">${signalHtml}</div>
  `;
}

function processStatusClass(category) {
  if (category === "no_touch" || category === "unmanaged") return "danger";
  if (category === "orchestration_tooling") return "attention";
  if (category === "authorized" || category === "mission_state") return "done";
  return "neutral";
}

function renderProcessControl(snapshot) {
  const container = byId("mcProcess");
  const countEl = byId("mcProcessCount");
  const process = snapshot.process_control || {};
  const changed = process.changed || [];
  const counts = process.counts || {};
  const gate = process.gate || "unknown";
  const gateClass = gate === "blocked" ? "danger" : gate === "attention" ? "attention" : "done";

  countEl.textContent = `${gate} · ${changed.length} changed paths`;

  const missingLinear = (process.missing_linear_tasks || []).length
    ? `
      <div class="mc-risk warning">
        <strong>Missing Linear gate</strong>
        <span>${escapeHtml((process.missing_linear_tasks || []).join(", "))}</span>
      </div>
    `
    : "";

  const rows = changed.length
    ? changed.slice(0, 18).map((item) => `
        <div class="mc-process-row">
          <span class="mc-status ${processStatusClass(item.category)}">${escapeHtml(item.category || "unknown")}</span>
          <code>${escapeHtml(item.path || "")}</code>
          <span>${escapeHtml(item.detail || "")}</span>
          <small>${escapeHtml([item.status, item.task_id].filter(Boolean).join(" · "))}</small>
        </div>
      `).join("")
    : `<div class="mc-empty">No changed paths in git status.</div>`;

  container.innerHTML = `
    <div class="mc-process-summary">
      <span class="mc-status ${gateClass}">${escapeHtml(gate)}</span>
      <strong>${escapeHtml(process.summary || "No process control data.")}</strong>
      <span>authorized: ${Number(counts.authorized || 0)} · unmanaged: ${Number(counts.unmanaged || 0)} · no-touch: ${Number(counts.no_touch || 0)} · tooling: ${Number(counts.orchestration_tooling || 0)}</span>
    </div>
    ${missingLinear}
    <div class="mc-process-list">${rows}</div>
  `;
}

const labels = {
  missing: "Missing",
  file: "File",
  directory: "Directory",
  unreadable: "Unreadable",
};

function byId(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  byId(id).textContent = value;
}

function formatDate(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function countExistingFiles(files) {
  if (!files) return 0;
  return Object.values(files).filter((item) => item.exists).length;
}

function renderEmptyStates(snapshot) {
  const items = [];
  if (snapshot.mission.empty_state) {
    items.push(["Mission", snapshot.mission.empty_state]);
  }
  if (snapshot.strategy.empty_state) {
    items.push(["Strategy", snapshot.strategy.empty_state]);
  }
  if (snapshot.orchestrator.empty_state) {
    items.push(["Orchestrator", snapshot.orchestrator.empty_state]);
  }

  const container = byId("emptyStates");
  if (items.length === 0) {
    container.innerHTML = `
      <div class="notice good">
        <strong>Runtime layers detected</strong>
        <span>Mission, strategy, and orchestrator sources are available from the current configuration.</span>
      </div>
    `;
    return;
  }
  container.innerHTML = items
    .map(
      ([title, text]) => `
        <div class="notice">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(text)}</span>
        </div>
      `,
    )
    .join("");
}

function renderDecisions(decisions) {
  const container = byId("decisionInbox");
  if (!decisions.length) {
    container.innerHTML = `
      <div class="empty">
        <strong>No decision items found</strong>
        <span>No source file currently reports a blocker, approval need, contract drift, or failed verification marker.</span>
      </div>
    `;
    return;
  }
  container.innerHTML = decisions
    .map(
      (item) => `
        <article class="item">
          <div>
            <strong>${escapeHtml(item.text || "Decision item")}</strong>
            <span>${escapeHtml(item.source)}:${escapeHtml(item.line)}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderHandoffs(handoffs) {
  const container = byId("handoffTrail");
  if (!handoffs.length) {
    container.innerHTML = `
      <div class="empty">
        <strong>No handoffs recorded</strong>
        <span>No role transition has been written to runtime.json or runlog.md yet.</span>
      </div>
    `;
    return;
  }
  container.innerHTML = handoffs
    .map((handoff) => {
      const from = [handoff.from_role, handoff.from_agent].filter(Boolean).join(" / ") || "Unknown source";
      const to = [handoff.to_role, handoff.to_agent].filter(Boolean).join(" / ") || "Unknown target";
      const task = handoff.task_id || "No task id";
      const linear = handoff.linear_issue_id || "No Linear";
      return `
        <article class="handoff-item">
          <div class="handoff-path">
            <span>${escapeHtml(from)}</span>
            <strong>-></strong>
            <span>${escapeHtml(to)}</span>
          </div>
          <dl>
            <div><dt>Task</dt><dd>${escapeHtml(task)}</dd></div>
            <div><dt>Linear</dt><dd>${escapeHtml(linear)}</dd></div>
            <div><dt>Status</dt><dd>${escapeHtml(handoff.status || "recorded")}</dd></div>
            <div><dt>Time</dt><dd>${escapeHtml(handoff.created_at || "No timestamp")}</dd></div>
            <div class="wide"><dt>Reason</dt><dd>${escapeHtml(handoff.reason || "No reason recorded")}</dd></div>
            <div class="wide"><dt>Source</dt><dd>${escapeHtml(handoff.source || "")}</dd></div>
          </dl>
        </article>
      `;
    })
    .join("");
}

function renderFileGrid(id, files) {
  const container = byId(id);
  const entries = Object.entries(files || {});
  if (!entries.length) {
    container.innerHTML = `<div class="empty"><strong>No files configured</strong></div>`;
    return;
  }
  container.innerHTML = entries
    .map(([name, item]) => {
      const status = item.exists ? labels[item.type] || item.type : labels.missing;
      const preview = item.preview ? `<pre>${escapeHtml(item.preview)}</pre>` : "";
      return `
        <article class="file-card ${item.exists ? "exists" : "missing"}">
          <div class="file-head">
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(status)}</span>
          </div>
          <p>${escapeHtml(item.path || "")}</p>
          ${preview}
        </article>
      `;
    })
    .join("");
}

function renderStrategy(snapshot) {
  const files = {
    ...snapshot.strategy.directories,
    ...snapshot.strategy.files,
  };
  renderFileGrid("strategyState", files);
}

function renderOrchestrator(orchestrator) {
  const scripts = orchestrator.scripts.length
    ? orchestrator.scripts.map((path) => `<li>${escapeHtml(path)}</li>`).join("")
    : "<li>No source scripts found</li>";
  const traces = orchestrator.pycache_traces.length
    ? orchestrator.pycache_traces.map((path) => `<li>${escapeHtml(path)}</li>`).join("")
    : "<li>No pycache traces found</li>";

  byId("orchestratorState").innerHTML = `
    <dl>
      <div><dt>Skill path</dt><dd>${escapeHtml(orchestrator.skill_path)}</dd></div>
      <div><dt>Source scripts</dt><dd><ul>${scripts}</ul></dd></div>
      <div><dt>Runtime traces</dt><dd><ul>${traces}</ul></dd></div>
    </dl>
  `;
}

function sessionValue(session, key, fallback = "Not set") {
  const value = session && session[key];
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function renderRuntime(snapshot) {
  const runtime = snapshot.mission.runtime || {};
  const sessions = Array.isArray(runtime.sessions) ? runtime.sessions : [];
  const container = byId("runtimeSessions");
  if (!sessions.length) {
    container.innerHTML = `
      <div class="empty">
        <strong>No active runtime sessions</strong>
        <span>No session is currently recorded in runtime.json.</span>
      </div>
    `;
    return;
  }
  container.innerHTML = sessions
    .map((session) => {
      const linearId = sessionValue(session, "linear_issue_id", "Missing Linear");
      const linearUrl = sessionValue(session, "linear_issue_url", "");
      const linearLabel = linearUrl
        ? `<a href="${escapeHtml(linearUrl)}" target="_blank" rel="noreferrer">${escapeHtml(linearId)}</a>`
        : `<span class="bad">${escapeHtml(linearId)}</span>`;
      return `
        <article class="item runtime-card">
          <div class="runtime-head">
            <strong>${escapeHtml(sessionValue(session, "task_id", "No task id"))}</strong>
            <span>${escapeHtml(sessionValue(session, "status", "unknown"))}</span>
          </div>
          <dl>
            <div><dt>Linear</dt><dd>${linearLabel}</dd></div>
            <div><dt>Title</dt><dd>${escapeHtml(sessionValue(session, "linear_title"))}</dd></div>
            <div><dt>Agent</dt><dd>${escapeHtml(sessionValue(session, "agent"))} / ${escapeHtml(sessionValue(session, "role"))}</dd></div>
            <div><dt>Phase</dt><dd>${escapeHtml(sessionValue(session, "phase"))}</dd></div>
            <div><dt>Worktree</dt><dd>${escapeHtml(sessionValue(session, "worktree"))}</dd></div>
            <div><dt>Branch</dt><dd>${escapeHtml(sessionValue(session, "branch"))}</dd></div>
            <div><dt>Last activity</dt><dd>${escapeHtml(sessionValue(session, "last_activity"))}</dd></div>
            <div><dt>Note</dt><dd>${escapeHtml(sessionValue(session, "current_note"))}</dd></div>
          </dl>
        </article>
      `;
    })
    .join("");
}

function renderGit(git) {
  const status = git.status.length ? git.status.join("\n") : "Working tree status is empty.";
  setText("gitStatus", status);
  setText("diffStat", git.diff_stat || "No unstaged diff summary.");
}

function renderRunlog(snapshot) {
  const lines = snapshot.mission.runlog_tail || [];
  setText("runlog", lines.length ? lines.join("\n") : "No mission runlog is available.");
}

function renderMissionTracking(snapshot) {
  const el = byId("missionTracking");
  if (!el) return;
  const name = snapshot.mission && snapshot.mission.active_mission_name;
  const reason = (snapshot.mission && snapshot.mission.resolution_reason) || "";
  if (!name) {
    el.classList.add("unresolved");
    el.textContent = `Mission: unresolved — ${reason || "no candidate"}`;
    return;
  }
  el.classList.remove("unresolved");
  el.innerHTML = `Mission: <strong>${escapeHtml(name)}</strong> <span class="reason">(${escapeHtml(reason)})</span>`;
}

function render(snapshot) {
  state.snapshot = snapshot;
  setText("generatedAt", `Snapshot: ${formatDate(snapshot.generated_at)}`);
  renderMissionTracking(snapshot);

  // Simplified view (always rendered, always visible).
  renderActiveWork(snapshot);
  renderPlanChecklist(snapshot);
  renderWorkflow(snapshot);
  renderWorkers(snapshot);
  renderVerificationGate(snapshot);
  renderProcessControl(snapshot);
  renderNeedsAttention(snapshot);
  renderRecentActivity(snapshot);

  // Advanced panels (rendered always; visibility gated by body.show-advanced).
  setText("decisionCount", String(snapshot.decisions.length));
  setText("missionFileCount", String(countExistingFiles(snapshot.mission.files)));
  setText("strategyItemCount", String(snapshot.strategy.items.length));
  setText("changedFileCount", String(snapshot.git.changed_files.length));
  const sessions = snapshot.mission.runtime && Array.isArray(snapshot.mission.runtime.sessions)
    ? snapshot.mission.runtime.sessions
    : [];
  setText("activeSessionCount", String(sessions.filter(isLiveSession).length));
  setText("handoffCount", String((snapshot.handoffs || []).length));

  renderEmptyStates(snapshot);
  renderDecisions(snapshot.decisions);
  renderHandoffs(snapshot.handoffs || []);
  renderRuntime(snapshot);
  renderFileGrid("missionFiles", snapshot.mission.files);
  renderOrchestrator(snapshot.orchestrator);
  renderStrategy(snapshot);
  renderGit(snapshot.git);
  renderRunlog(snapshot);
}

function initAdvancedToggle() {
  const toggle = byId("toggleAdvanced");
  if (!toggle) return;
  const stored = window.localStorage.getItem("mc.showAdvanced") === "1";
  toggle.checked = stored;
  document.body.classList.toggle("show-advanced", stored);
  toggle.addEventListener("change", () => {
    document.body.classList.toggle("show-advanced", toggle.checked);
    window.localStorage.setItem("mc.showAdvanced", toggle.checked ? "1" : "0");
  });
}

async function refresh() {
  setText("refreshState", "Refreshing");
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const snapshot = await response.json();
    render(snapshot);
    setText("refreshState", "Live polling");
  } catch (error) {
    setText("refreshState", `Error: ${error.message}`);
  }
}

async function refreshLive() {
  try {
    const response = await fetch("/api/live", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const live = await response.json();
    state.live = live;
    renderRepoActivity(live);
  } catch (error) {
    renderRepoActivity({ errors: [`/api/live unreachable: ${error.message}`], commits: [], pull_requests: [] });
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderLiveAgents(data) {
  const container = byId("mcLiveAgents");
  const countEl = byId("mcLiveAgentsCount");
  if (!container) return;
  if (!data || !data.sessions || data.sessions.length === 0) {
    container.innerHTML = '<div class="mc-empty">No agent activity captured.</div>';
    if (countEl) countEl.textContent = "0 sessions";
    return;
  }
  if (countEl) countEl.textContent = `${data.sessions.length} session${data.sessions.length === 1 ? "" : "s"} · ${data.total_events} events`;
  const now = Date.now();
  const html = data.sessions.map((sess) => {
    const lastMs = sess.last_ts ? Date.parse(sess.last_ts) : 0;
    const ageSec = Math.max(0, Math.floor((now - lastMs) / 1000));
    const isActive = ageSec < 60;
    const dotColor = isActive ? "#10b981" : ageSec < 300 ? "#f59e0b" : "#94a3b8";
    const agentColor = sess.agent === "claude-code" ? "#8b5cf6" : sess.agent === "codex" ? "#06b6d4" : "#6b7280";
    const ageLabel = ageSec < 60 ? `${ageSec}s ago` : ageSec < 3600 ? `${Math.floor(ageSec/60)}m ago` : `${Math.floor(ageSec/3600)}h ago`;
    const eventsHtml = (sess.events || []).slice(0, 6).map((e) => {
      const t = escapeHtml(e.tool || "");
      const tgt = escapeHtml(e.target || "");
      const ts = (e.ts || "").slice(11, 19);
      return `<div class="mc-live-event"><span class="mc-live-ts">${ts}</span> <span class="mc-live-tool">${t}</span>${tgt ? ` <span class="mc-live-target">${tgt}</span>` : ""}</div>`;
    }).join("");
    return `
      <div class="mc-live-session">
        <div class="mc-live-head">
          <span class="mc-live-dot" style="background:${dotColor}"></span>
          <span class="mc-live-agent" style="color:${agentColor}">${escapeHtml(sess.agent)}</span>
          <span class="mc-live-session-id">${escapeHtml(sess.session)}</span>
          <span class="mc-live-count">${sess.event_count} events</span>
          <span class="mc-live-age">${ageLabel}</span>
        </div>
        <div class="mc-live-events">${eventsHtml}</div>
      </div>`;
  }).join("");
  container.innerHTML = html;
}

async function refreshActivity() {
  try {
    const response = await fetch("/api/activity", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderLiveAgents(data);
  } catch (error) {
    const container = byId("mcLiveAgents");
    if (container) container.innerHTML = `<div class="mc-empty">/api/activity unreachable: ${escapeHtml(error.message)}</div>`;
  }
}

initAdvancedToggle();
refresh();
refreshLive();
refreshActivity();
state.timer = window.setInterval(refresh, 3000);
state.liveTimer = window.setInterval(refreshLive, 30000);
state.activityTimer = window.setInterval(refreshActivity, 3000);
