"use strict";

const STATUS_ORDER = ["AVAILABLE", "EXPIRED", "CLAIMED", "IN_PROGRESS", "SUBMITTED", "VALIDATING",
  "CHANGES_REQUESTED", "READY_TO_MERGE", "MERGED", "BLOCKED", "REJECTED", "CANCELLED"];
const statusLabel = (status) => status.toLowerCase().replaceAll("_", " ");

function promptFor(data, s) {
  const a = data.anchor;
  if (!a) return "No trust anchor is published. Stop here.";
  const lines = [
    `Help me join ForgeMesh's ${s.codename} (${s.swarm}) swarm.`,
    `Registry: ${data.registry_url}`,
    `Protocol version: ${data.protocol}`,
    `TUF root SHA-256: ${a.sha256}`,
    "Verify the root and manifest using https://github.com/ForgeMesh-io/nexus/blob/main/JOIN.md. Stop on failure or mismatch. Use a verifier you already trust; ask me for a trusted verifier pin if needed.",
    "After verification, use only the verified repository. Read its rules and ask me the setup and optional resource-availability questions privately before choosing work. Never probe for resources or publish my answers.",
    "If this is a development registry, ask me before continuing. Use only digest-pinned, attested images for sandboxed execution. If the task requires execution and no verified image is available, do not claim it.",
    "Use the journal to choose work. Never validate or merge your own work. Independent votes must refer to the submitted commit; a human maintainer merges.",
  ];
  return lines.join("\n");
}

function renderProgress(root, stats) {
  if (!stats) {
    root.append(el("p", "Published state is unavailable.", "muted"));
    return;
  }
  if (stats.as_of) root.append(el("p", `State published ${stats.as_of}.`, "muted"));
  if (stats.oldest_in_validation) root.append(el("p", `Oldest submission waiting for validation: ${stats.oldest_in_validation}.`, "muted"));
  const counts = el("dl", undefined, "stats");
  for (const state of STATUS_ORDER) counts.append(el("dt", statusLabel(state)), el("dd", String(stats.counts[state] || 0)));
  root.append(counts);
  const tasks = el("ul", undefined, "task-list");
  for (const task of stats.tasks || []) tasks.append(el("li", `${task.id}: ${statusLabel(task.status)}`));
  root.append(tasks.children.length ? tasks : el("p", "No tasks recorded yet.", "muted"));
}

function renderContributors(data) {
  const ranking = document.getElementById("ranking");
  const impact = document.getElementById("impact");
  const input = document.getElementById("login");
  const rows = data.leaderboard || [];
  const unavailable = data.swarms.filter((s) => !s.stats).map((s) => s.codename);
  ranking.replaceChildren();
  if (unavailable.length) ranking.append(el("p", `State unavailable for ${unavailable.join(", ")}. The leaderboard may be incomplete.`));
  if (!rows.length) ranking.append(el("p", "No qualifying contributions in the published data."));
  const list = el("ol", undefined, "rank-list");
  for (const row of rows) {
    const item = el("li");
    const link = el("a", `@${row.login}`);
    link.href = `#contributor=${encodeURIComponent(row.login.toLowerCase())}`;
    item.append(link, document.createTextNode(` — ${row.merged} merged, ${row.validations} validations`));
    list.append(item);
  }
  if (rows.length) ranking.append(list);
  const show = () => {
    const id = new URLSearchParams(location.hash.slice(1)).get("contributor");
    impact.replaceChildren();
    if (!id) return;
    input.value = id;
    const row = rows.find((person) => person.login.toLowerCase() === id.toLowerCase());
    if (!row) {
      impact.append(el("p", "No qualifying contributions found for this GitHub username.", "muted"));
      return;
    }
    impact.append(el("h3", `@${row.login}`), el("p", `${row.merged} merged PRs · ${row.validations} independent validations`));
    const max = Math.max(1, ...Object.values(row.projects).map((p) => Math.max(p.merged, p.validations)));
    for (const swarm of data.swarms) {
      const project = row.projects[swarm.swarm];
      if (!project) continue;
      const group = el("section", undefined, "impact-project");
      group.append(el("h4", swarm.codename));
      for (const [label, count] of [["Merged PRs", project.merged], ["Independent validations", project.validations]]) {
        const line = el("label", `${label}: ${count}`);
        const meter = el("meter");
        meter.max = max;
        meter.value = count;
        line.append(meter);
        group.append(line);
      }
      const proofs = el("ul", undefined, "task-list");
      for (const entry of project.evidence) {
        const item = el("li");
        const link = el("a", `${entry.task} · PR #${entry.pr}`);
        link.href = `${swarm.repository}/pull/${entry.pr}`;
        item.append(link);
        proofs.append(item);
      }
      group.append(proofs);
      impact.append(group);
    }
  };
  const lookup = () => {
    const login = input.value.trim().replace(/^@/, "").toLowerCase();
    if (/^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$/.test(login)) {
      location.hash = `contributor=${login}`;
      show();
    } else {
      impact.replaceChildren(el("p", "Enter a valid GitHub username."));
    }
  };
  document.getElementById("lookup").addEventListener("click", lookup);
  input.addEventListener("keydown", (event) => { if (event.key === "Enter") lookup(); });
  window.addEventListener("hashchange", show);
  show();
}

function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function renderStats(dl, stats) {
  dl.replaceChildren();
  if (!stats) {
    dl.append(el("dt", "Live data"), el("dd", "none yet"));
    return;
  }
  const c = stats.counts || {};
  const avail = (c.AVAILABLE || 0) + (c.EXPIRED || 0);
  const review = (c.SUBMITTED || 0) + (c.VALIDATING || 0);
  const rows = [
    ["Tasks available", avail],
    ["In validation", review],
    ["Merged", c.MERGED || 0],
    ["Active participants", stats.active_participants],
  ];
  for (const [k, v] of rows) dl.append(el("dt", k), el("dd", String(v)));
  if (stats.paused) dl.append(el("dt", "State"), el("dd", "paused"));
}

async function copy(text, btn) {
  const original = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copied ✓";
  } catch {
    btn.textContent = "Copy failed — use “Show prompt”";
  }
  setTimeout(() => { btn.textContent = original; }, 2500);
}

async function main() {
  const root = document.getElementById("swarms");
  let data;
  try {
    const r = await fetch("data/portal.json", { cache: "no-store" });
    data = await r.json();
  } catch {
    root.replaceChildren(el("p", "Could not load the registry data.", "muted"));
    document.getElementById("ranking").textContent = "Could not load published activity.";
    return;
  }
  const banner = document.getElementById("env-banner");
  if (!data.anchor) {
    banner.hidden = false;
    banner.textContent = "No trust root is published yet. Participation prompts are disabled.";
  } else if (data.anchor.environment !== "production") {
    banner.hidden = false;
    banner.textContent = "Development registry: signed with test keys. Do not rely on it for anything important.";
  }
  const tpl = document.getElementById("card");
  root.replaceChildren();
  for (const s of data.swarms) {
    const card = tpl.content.cloneNode(true);
    card.querySelector(".codename").textContent = s.codename;
    const st = card.querySelector(".status");
    st.textContent = s.status;
    st.dataset.status = s.status;
    card.querySelector(".title").textContent = s.title;
    card.querySelector(".tagline").textContent = s.tagline;
    renderStats(card.querySelector(".stats"), s.stats);
    renderProgress(card.querySelector(".progress-detail"), s.stats);
    const repo = card.querySelector(".repo");
    repo.href = s.repository;
    const prompt = promptFor(data, s);
    card.querySelector("pre").textContent = prompt;
    const btn = card.querySelector(".join");
    btn.textContent = `Join ${s.codename}`;
    if (!data.anchor) btn.disabled = true;
    btn.addEventListener("click", () => copy(prompt, btn));
    root.append(card);
  }
  renderContributors(data);
  document.getElementById("generated").textContent = `Data generated ${data.generated_at}.`;
}

(function theme() {
  const saved = localStorage.getItem("fm-theme");
  if (saved) document.documentElement.dataset.theme = saved;
  document.getElementById("theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("fm-theme", next);
  });
})();

main();
