// Ariadne process graph inspector -- plain JS, no build step (CLAUDE.md:
// no framework, no bundler at this size). Talks only to this server's own
// /api/* endpoints; never fetches anything off-host.
//
// The one job that matters: get from any rendered fact to the verbatim
// evidence text it came from in a single click, without leaving the page.

(() => {
  "use strict";

  const state = {
    nodesById: new Map(),
    counts: {},
    selectedId: null,
    evidenceCache: new Map(),
    diagramSvg: null,
    // "100": render at natural size (legible labels, scrolls both axes).
    // "fit": scale down to the container width (may be illegible on wide
    // graphs, but useful for a quick overview). Default to legible.
    diagramZoom: "100",
  };

  const sidebarEl = document.getElementById("sidebar");
  const detailEl = document.getElementById("detail-pane");
  const diagramEl = document.getElementById("mermaid-container");
  const statusEl = document.getElementById("status");
  const zoom100Button = document.getElementById("zoom-100");
  const zoomFitButton = document.getElementById("zoom-fit");

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Mirrors ariadne.export._sanitize_id -- needed to map a graph node id to
  // the id mermaid assigns its rendered SVG element, so clicking the
  // diagram can select the same node as clicking the sidebar.
  function sanitizeMermaidId(nodeId) {
    let sanitized = String(nodeId).replace(/[^A-Za-z0-9_]/g, "_");
    if (!sanitized || !/^[A-Za-z_]/.test(sanitized[0])) {
      sanitized = `n_${sanitized}`;
    }
    return sanitized;
  }

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `${url} -> ${response.status}`);
    }
    return response.json();
  }

  function isUnverified(node) {
    return !node.is_evidence && (!node.evidence_ids || node.evidence_ids.length === 0);
  }

  function nodeFlags(node) {
    const flags = [];
    if (node.type === "Exception") flags.push("exception");
    if (isUnverified(node)) flags.push("unverified");
    return flags;
  }

  function renderSidebar(nodes, counts) {
    const byType = new Map();
    for (const node of nodes) {
      if (!byType.has(node.type)) byType.set(node.type, []);
      byType.get(node.type).push(node);
    }
    const types = Array.from(byType.keys()).sort();

    sidebarEl.innerHTML = "";
    for (const type of types) {
      const group = document.createElement("div");
      group.className = "type-group";

      const heading = document.createElement("h2");
      heading.textContent = `${type} (${counts[type] ?? byType.get(type).length})`;
      group.appendChild(heading);

      const items = byType.get(type).slice().sort((a, b) => a.label.localeCompare(b.label));
      for (const node of items) {
        const flags = nodeFlags(node);
        const item = document.createElement("div");
        item.className = ["node-item", ...flags].join(" ");
        item.dataset.nodeId = node.id;
        item.setAttribute("role", "button");
        item.setAttribute("tabindex", "0");

        item.title = node.label;

        const label = document.createElement("span");
        label.className = "node-label";
        label.textContent = node.label;
        item.appendChild(label);

        const flagSpan = document.createElement("span");
        flagSpan.className = "flag";
        if (flags.includes("exception")) flagSpan.textContent += "⚠ ";
        if (flags.includes("unverified")) flagSpan.textContent += "✗ evidence";
        item.appendChild(flagSpan);

        item.addEventListener("click", () => selectNode(node.id));
        item.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectNode(node.id);
          }
        });
        group.appendChild(item);
      }
      sidebarEl.appendChild(group);
    }
  }

  function highlightSelection() {
    for (const el of sidebarEl.querySelectorAll(".node-item")) {
      el.classList.toggle("selected", el.dataset.nodeId === state.selectedId);
    }
  }

  // --- Diagram -------------------------------------------------------

  async function renderDiagram() {
    let mermaidSource;
    try {
      const body = await fetchJson("/api/mermaid");
      mermaidSource = body.mermaid;
    } catch (error) {
      renderFallbackDiagram();
      return;
    }

    if (typeof window.mermaid === "undefined") {
      renderFallbackDiagram();
      return;
    }

    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    try {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        // Mermaid renders labels inside a foreignObject and parses them as
        // HTML by default -- downstream of any escaping we do, "strict"
        // security level only strips event handlers, not tags like <img>.
        // A node name from LLM-extracted graph content containing
        // `<img src="https://evil.example/x">` would make the browser issue
        // an outbound request when the diagram renders, breaking the
        // "no network calls beyond this server" constraint. Forcing SVG
        // <text> labels instead of HTML eliminates this vector entirely
        // rather than trying to blacklist tags.
        htmlLabels: false,
        flowchart: { htmlLabels: false },
        theme: "base",
        themeVariables: dark ? DARK_THEME_VARS : LIGHT_THEME_VARS,
      });
      const { svg } = await window.mermaid.render("ariadne-diagram", mermaidSource);
      diagramEl.innerHTML = svg;
      state.diagramSvg = diagramEl.querySelector("svg");
      applyDiagramZoom();
      bindDiagramClicks();
      markExceptionNodes();
    } catch (error) {
      renderFallbackDiagram();
    }
  }

  // Cool-neutral "system inference" palette for the diagram -- see app.js
  // header note on the trust-boundary visual language.
  const LIGHT_THEME_VARS = {
    background: "#ffffff",
    primaryColor: "#eef1f5",
    primaryBorderColor: "#5b6b82",
    primaryTextColor: "#1a1a1a",
    lineColor: "#5b6b82",
    secondaryColor: "#eef6ff",
    tertiaryColor: "#f6f6f7",
    clusterBkg: "#f6f6f7",
    clusterBorder: "#c3ccd6",
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  };

  const DARK_THEME_VARS = {
    background: "#1a1a1a",
    primaryColor: "#2a2f38",
    primaryBorderColor: "#8fa3bd",
    primaryTextColor: "#e8e8e8",
    lineColor: "#8fa3bd",
    secondaryColor: "#17263a",
    tertiaryColor: "#242424",
    clusterBkg: "#20242b",
    clusterBorder: "#3a4250",
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  };

  // Mermaid renders its SVG with width="100%" + a max-width style so it
  // shrinks to fit the column -- on any real (wide) flowchart that scales
  // labels down to illegible sizes. Strip that and size the SVG from its
  // own viewBox instead, so labels render at their natural ~16px and the
  // container scrolls (both axes) rather than the diagram shrinking.
  function applyDiagramZoom() {
    const svg = state.diagramSvg;
    if (!svg) return;

    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.style.maxWidth = "none";

    const viewBox = svg.getAttribute("viewBox");
    if (state.diagramZoom === "100" && viewBox) {
      const parts = viewBox.split(/\s+/).map(Number);
      const [, , vbWidth, vbHeight] = parts;
      if (vbWidth > 0 && vbHeight > 0) {
        svg.style.width = `${vbWidth}px`;
        svg.style.height = `${vbHeight}px`;
      }
    } else {
      // "fit": let it shrink to the container width, preserving aspect
      // ratio via the viewBox -- an intentional, opt-in trade of
      // legibility for overview.
      svg.style.width = "100%";
      svg.style.height = "auto";
    }

    if (zoom100Button && zoomFitButton) {
      zoom100Button.setAttribute("aria-pressed", String(state.diagramZoom === "100"));
      zoomFitButton.setAttribute("aria-pressed", String(state.diagramZoom === "fit"));
    }
  }

  if (zoom100Button) {
    zoom100Button.addEventListener("click", () => {
      state.diagramZoom = "100";
      applyDiagramZoom();
    });
  }
  if (zoomFitButton) {
    zoomFitButton.addEventListener("click", () => {
      state.diagramZoom = "fit";
      applyDiagramZoom();
    });
  }

  function bindDiagramClicks() {
    for (const node of state.nodesById.values()) {
      const sanitized = sanitizeMermaidId(node.id);
      const matches = diagramEl.querySelectorAll(
        `[id^="flowchart-${sanitized}-"], #${sanitized}`,
      );
      for (const el of matches) {
        el.style.cursor = "pointer";
        el.setAttribute("tabindex", "0");
        el.addEventListener("click", () => selectNode(node.id));
        el.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectNode(node.id);
          }
        });
      }
    }
  }

  // Exception nodes carry the tribal knowledge this tool exists to surface
  // -- they must draw the eye first in the diagram, not just the sidebar.
  function markExceptionNodes() {
    for (const node of state.nodesById.values()) {
      if (node.type !== "Exception") continue;
      const sanitized = sanitizeMermaidId(node.id);
      const matches = diagramEl.querySelectorAll(`[id^="flowchart-${sanitized}-"]`);
      for (const el of matches) {
        el.classList.add("diagram-exception");
      }
    }
  }

  // Used when mermaid can't be rendered (e.g. no JS SVG support). Built
  // straight from /api/graph data so it still reflects the real graph, and
  // every node stays one click from its detail/evidence.
  function renderFallbackDiagram() {
    const toolbar = document.getElementById("diagram-toolbar");
    if (toolbar) toolbar.hidden = true;

    const nodes = Array.from(state.nodesById.values());
    const processTypes = new Set(["ProcessStep", "Decision", "Exception"]);
    const processNodes = nodes.filter((n) => processTypes.has(n.type));

    const container = document.createElement("div");
    container.className = "fallback-diagram";

    const note = document.createElement("p");
    note.className = "fallback-note";
    note.textContent =
      "Structured fallback view (mermaid diagram unavailable in this environment).";
    container.appendChild(note);

    if (processNodes.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No process steps in this graph yet.";
      container.appendChild(empty);
    } else {
      const group = document.createElement("div");
      group.className = "role-group";
      const heading = document.createElement("h3");
      heading.textContent = "Process steps";
      group.appendChild(heading);

      for (const node of processNodes.sort((a, b) => a.id.localeCompare(b.id))) {
        const flags = nodeFlags(node);
        const span = document.createElement("span");
        span.className = ["fallback-node", ...flags].join(" ");
        span.textContent = node.label;
        span.setAttribute("role", "button");
        span.setAttribute("tabindex", "0");
        span.addEventListener("click", () => selectNode(node.id));
        group.appendChild(span);
      }
      container.appendChild(group);
    }

    diagramEl.innerHTML = "";
    diagramEl.appendChild(container);
  }

  // --- Detail panel ----------------------------------------------------

  function renderProperties(properties) {
    const entries = Object.entries(properties || {});
    if (entries.length === 0) return "";
    const rows = entries
      .map(
        ([key, value]) =>
          `<tr><td class="key">${escapeHtml(key)}</td><td>${escapeHtml(
            typeof value === "object" ? JSON.stringify(value) : value,
          )}</td></tr>`,
      )
      .join("");
    return `<table class="props-table">${rows}</table>`;
  }

  // Evidence.properties is schema-free -- pipeline evidence carries "text",
  // LLM-extracted evidence may carry "summary" or other free-form keys
  // (subject/from/date/...). Never show a bare "no text recorded" placeholder
  // when the node actually has content under a different key.
  function renderEvidenceBody(evidence) {
    const { id, source, text, summary, ...rest } = evidence;
    const quote = text ?? summary;
    let html = "";
    if (quote) {
      html += `<blockquote class="evidence-quote">${escapeHtml(quote)}</blockquote>`;
    }
    const restEntries = Object.entries(rest).filter(([, v]) => v !== null && v !== undefined);
    if (!quote && restEntries.length === 0) {
      html += `<p class="evidence-quote evidence-empty">(no verbatim text recorded for this evidence node)</p>`;
    } else if (restEntries.length > 0) {
      const rows = restEntries
        .map(
          ([key, value]) =>
            `<tr><td class="key">${escapeHtml(key)}</td><td>${escapeHtml(value)}</td></tr>`,
        )
        .join("");
      html += `<table class="props-table evidence-meta">${rows}</table>`;
    }
    html += `<div class="evidence-source">source: ${escapeHtml(source ?? "unknown")}</div>`;
    return html;
  }

  async function toggleEvidence(evidenceId, bodyEl, button) {
    const isOpen = bodyEl.dataset.open === "true";
    if (isOpen) {
      bodyEl.hidden = true;
      bodyEl.dataset.open = "false";
      button.textContent = "show evidence";
      button.setAttribute("aria-expanded", "false");
      return;
    }

    button.textContent = "loading…";
    try {
      let evidence = state.evidenceCache.get(evidenceId);
      if (!evidence) {
        evidence = await fetchJson(`/api/evidence/${encodeURIComponent(evidenceId)}`);
        state.evidenceCache.set(evidenceId, evidence);
      }
      bodyEl.innerHTML = renderEvidenceBody(evidence);
      bodyEl.hidden = false;
      bodyEl.dataset.open = "true";
      button.textContent = "hide evidence";
      button.setAttribute("aria-expanded", "true");
    } catch (error) {
      bodyEl.innerHTML = `<div class="evidence-source">could not load evidence: ${escapeHtml(error.message)}</div>`;
      bodyEl.hidden = false;
      bodyEl.dataset.open = "true";
      button.textContent = "hide evidence";
      button.setAttribute("aria-expanded", "true");
    }
  }

  function renderFact(fact) {
    const item = document.createElement("li");
    item.className = "fact-item";

    const header = document.createElement("div");
    header.className = "fact-header";

    const text = document.createElement("span");
    const arrow = fact.direction === "out" ? "→" : "←";

    const edgeType = document.createElement("span");
    edgeType.className = "edge-type";
    edgeType.textContent = `${fact.edge_type} ${arrow} `;
    text.appendChild(edgeType);

    const neighborLink = document.createElement("span");
    neighborLink.className = "neighbor-link";
    neighborLink.textContent = fact.neighbor_label;
    neighborLink.setAttribute("role", "button");
    neighborLink.setAttribute("tabindex", "0");
    neighborLink.addEventListener("click", () => selectNode(fact.neighbor_id));
    neighborLink.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(fact.neighbor_id);
      }
    });
    text.appendChild(neighborLink);
    header.appendChild(text);
    item.appendChild(header);

    if (!fact.evidence_ids || fact.evidence_ids.length === 0) {
      const flag = document.createElement("span");
      flag.className = "badge unverified";
      flag.textContent = "no evidence";
      header.appendChild(flag);
    } else {
      for (const evidenceId of fact.evidence_ids) {
        const button = document.createElement("button");
        button.className = "evidence-toggle";
        button.textContent = "show evidence";
        button.setAttribute("aria-expanded", "false");
        // The thread: a physical line from the claim down into its quoted
        // source, so the eye follows claim -> evidence (Ariadne's thread
        // leading back out of the labyrinth).
        const thread = document.createElement("div");
        thread.className = "evidence-thread";
        thread.hidden = true;
        const body = document.createElement("div");
        body.className = "evidence-body";
        body.hidden = true;
        button.addEventListener("click", async () => {
          await toggleEvidence(evidenceId, body, button);
          thread.hidden = body.hidden;
        });
        item.appendChild(button);
        item.appendChild(thread);
        item.appendChild(body);
      }
    }

    return item;
  }

  async function selectNode(nodeId) {
    state.selectedId = nodeId;
    highlightSelection();
    detailEl.innerHTML = "<p class=\"empty-state\">loading…</p>";

    let payload;
    try {
      payload = await fetchJson(`/api/nodes/${encodeURIComponent(nodeId)}`);
    } catch (error) {
      detailEl.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
      return;
    }

    const { node, facts } = payload;
    const flags = nodeFlags(node);

    const badges = flags
      .map((flag) => `<span class="badge ${flag}">${flag}</span>`)
      .join(" ");

    let html = `<h2>${escapeHtml(node.label)}</h2>`;
    html += `<p class="node-id">${escapeHtml(node.id)}</p>`;
    html += `<p><strong>${escapeHtml(node.type)}</strong> ${badges}</p>`;
    html += renderProperties(node.properties);

    detailEl.innerHTML = html;

    const factsHeading = document.createElement("h3");
    factsHeading.textContent = `Facts (${facts.length})`;
    detailEl.appendChild(factsHeading);

    if (facts.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No incident facts.";
      detailEl.appendChild(empty);
    } else {
      const list = document.createElement("ul");
      list.className = "fact-list";
      for (const fact of facts) {
        list.appendChild(renderFact(fact));
      }
      detailEl.appendChild(list);
    }
  }

  // --- Boot --------------------------------------------------------------

  async function init() {
    try {
      const graph = await fetchJson("/api/graph");
      for (const node of graph.nodes) {
        state.nodesById.set(node.id, node);
      }
      state.counts = graph.counts;
      statusEl.textContent = `${graph.nodes.length} nodes, ${graph.edges.length} edges`;
      renderSidebar(graph.nodes, graph.counts);
      await renderDiagram();
    } catch (error) {
      statusEl.textContent = `failed to load graph: ${error.message}`;
    }
  }

  init();
})();
