"""HTML shells for the public demo pages."""

PIPELINE_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Jikai Trace</title>
  <style>
    :root {
      --bg: #01222A;
      --ink: #F3F4F6;
      --muted: #D1D5DB;
      --line: #374151CC;
      --panel: #0B2B33;
      --field: #163A44;
      --green: #195D6C;
      --green-2: #0F3F49;
      --secondary: #023643;
      --blue: #0EA5E9;
      --amber: #6B8790;
      --red: #EF4444;
      --soft: #163A44;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 20px;
      font-size: 14px;
      line-height: 20px;
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    .wrap {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }
    .topbar {
      min-height: 68px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 30px;
      line-height: 32px;
      font-weight: 400;
      letter-spacing: 1px;
    }
    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 14px;
      line-height: 20px;
    }
    nav.links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 14px;
      line-height: 20px;
    }
    a {
      color: var(--blue);
      text-decoration: none;
      font-weight: 400;
    }
    main {
      padding: 16px 0 28px;
      display: grid;
      gap: 12px;
    }
    .toolbar, .metric, .stage {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: end;
      padding: 12px;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      text-transform: none;
    }
    input, button {
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--field);
      color: var(--ink);
      font: inherit;
      padding: 0 16px;
    }
    button {
      background: var(--green);
      border-color: var(--green);
      color: var(--ink);
      font-weight: 400;
      cursor: pointer;
      white-space: nowrap;
    }
    .secondary {
      background: var(--secondary);
      border-color: var(--line);
      color: var(--muted);
    }
    .toggles {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 48px;
      padding: 0 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--field);
      color: var(--muted);
      font-size: 12px;
      text-transform: none;
    }
    .toggle input {
      min-height: 0;
      width: auto;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      min-height: 76px;
      padding: 12px;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: none;
      font-weight: 400;
    }
    .metric .value {
      margin-top: 7px;
      font-size: 20px;
      line-height: 32px;
      font-weight: 400;
      overflow-wrap: anywhere;
    }
    .trace-grid {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }
    .rail {
      position: sticky;
      top: 12px;
      display: grid;
      gap: 7px;
    }
    .rail button {
      width: 100%;
      min-height: 48px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--panel);
      color: var(--ink);
      border-color: var(--line);
      font-weight: 400;
      text-align: left;
    }
    .rail button.active {
      border-color: var(--green);
      background: var(--field);
      box-shadow: inset 4px 0 0 var(--blue);
    }
    .badge {
      min-width: 74px;
      padding: 3px 8px;
      border-radius: 999px;
      text-align: center;
      font-size: 12px;
      font-weight: 400;
      background: var(--soft);
      color: var(--muted);
    }
    .badge.complete { background: var(--field); color: var(--blue); }
    .badge.warning { background: var(--secondary); color: var(--amber); }
    .badge.error { background: var(--secondary); color: var(--red); }
    .stage {
      display: none;
      min-height: 560px;
      padding: 16px;
    }
    .stage.active { display: block; }
    h2 {
      margin: 0 0 10px;
      font-size: 20px;
      line-height: 32px;
      font-weight: 400;
      letter-spacing: 1px;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--field);
      max-height: 470px;
      overflow: auto;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .items {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: var(--field);
    }
    .item strong {
      display: block;
      margin-bottom: 5px;
    }
    .item p {
      margin: 6px 0 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .failures {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }
    .failure {
      border: 1px solid var(--red);
      color: var(--red);
      background: var(--secondary);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      font-weight: 400;
    }
    @media (max-width: 840px) {
      .topbar {
        min-height: 0;
        align-items: flex-start;
        flex-direction: column;
        padding: 14px 0;
      }
      .toolbar { grid-template-columns: 1fr; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .trace-grid { grid-template-columns: 1fr; }
      .rail { position: static; }
      .stage { min-height: 0; }
      .toggles button { flex: 1 1 130px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <div>
        <h1>Jikai Trace</h1>
        <div class="subtitle" id="trace-mode">fixture trace</div>
      </div>
      <nav class="links" aria-label="demo navigation">
        <a href="/demo">Practice</a>
        <a href="/health">Health</a>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <section class="toolbar">
      <label>Topics
        <input id="topics" type="text" value="negligence, causation">
      </label>
      <div class="toggles">
        <label class="toggle"><input id="live" type="checkbox"> live</label>
        <label class="toggle"><input id="prompt" type="checkbox"> prompt</label>
        <label class="toggle"><input id="provider" type="checkbox"> provider</label>
        <button id="run" type="button">Run trace</button>
      </div>
    </section>
    <section class="summary" id="summary"></section>
    <section class="trace-grid">
      <nav class="rail" id="rail" aria-label="pipeline stages"></nav>
      <article id="stage-host"></article>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const state = { trace: null, active: 0 };
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));

    function metric(label, value) {
      return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
    }

    function statusClass(status) {
      return ["complete", "warning", "error"].includes(status) ? status : "";
    }

    function renderDetails(stage) {
      const d = stage.details || {};
      if (stage.id === "retrieval" && Array.isArray(d.items)) {
        const items = d.items.map((item) => `
          <div class="item">
            <strong>${esc(item.case_name || item.id)}</strong>
            <div>${esc((item.topics || []).join(", "))} | ${esc(item.source || "local corpus")}</div>
            <p>${esc(item.excerpt || "")}</p>
          </div>`).join("");
        const meta = {...d};
        delete meta.items;
        const metaBlock = Object.keys(meta).length ? `<pre>${esc(JSON.stringify(meta, null, 2))}</pre>` : "";
        return `${metaBlock}<div class="items">${items}</div>`;
      }
      if (stage.id === "validation" && Array.isArray(d.failure_reasons) && d.failure_reasons.length) {
        const failures = d.failure_reasons.map((reason) => `<span class="failure">${esc(reason)}</span>`).join("");
        return `<div class="failures">${failures}</div><pre>${esc(JSON.stringify(d, null, 2))}</pre>`;
      }
      return `<pre>${esc(JSON.stringify(d, null, 2))}</pre>`;
    }

    function render(trace) {
      state.trace = trace;
      const summary = trace.summary || {};
      $("trace-mode").textContent = `${trace.mode} trace | ${trace.generated_at}`;
      $("summary").innerHTML = [
        metric("result", summary.passed ? "passed" : "needs review"),
        metric("topics", (summary.topics || []).join(", ")),
        metric("corpus", summary.corpus_pack || ""),
        metric("retrieved", summary.retrieved_count ?? 0)
      ].join("");

      const stages = trace.stages || [];
      if (state.active >= stages.length) state.active = 0;
      $("rail").innerHTML = stages.map((stage, idx) => `
        <button type="button" class="${idx === state.active ? "active" : ""}" data-idx="${idx}">
          <span>${esc(stage.label)}</span>
          <span class="badge ${statusClass(stage.status)}">${esc(stage.status)}</span>
        </button>`).join("");
      $("stage-host").innerHTML = stages.map((stage, idx) => `
        <section class="stage ${idx === state.active ? "active" : ""}" data-idx="${idx}">
          <h2>${esc(stage.label)}</h2>
          ${renderDetails(stage)}
        </section>`).join("");
      document.querySelectorAll("#rail button").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.active = Number(btn.dataset.idx);
          render(state.trace);
        });
      });
    }

    async function loadTrace() {
      $("run").disabled = true;
      const topics = $("topics").value.split(",").map((v) => v.trim()).filter(Boolean);
      const params = new URLSearchParams({
        topics: topics.join(","),
        live: $("live").checked ? "true" : "false",
        expose_prompt: $("prompt").checked ? "true" : "false",
        expose_provider: $("provider").checked ? "true" : "false"
      });
      try {
        const res = await fetch(`/demo/pipeline/trace?${params.toString()}`);
        if (!res.ok) throw new Error(await res.text());
        render(await res.json());
      } catch (err) {
        $("stage-host").innerHTML = `<section class="stage active"><h2>Error</h2><pre>${esc(err.message)}</pre></section>`;
      } finally {
        $("run").disabled = false;
      }
    }

    $("run").addEventListener("click", loadTrace);
    loadTrace();
  </script>
</body>
</html>
"""


GENERATION_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Jikai Practice</title>
  <style>
    :root {
      --bg: #01222A;
      --ink: #F3F4F6;
      --muted: #D1D5DB;
      --line: #374151CC;
      --panel: #0B2B33;
      --field: #163A44;
      --green: #195D6C;
      --green-2: #0F3F49;
      --secondary: #023643;
      --blue: #0EA5E9;
      --amber: #6B8790;
      --red: #EF4444;
      --soft: #163A44;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    .wrap {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }
    .topbar {
      min-height: 68px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 30px;
      line-height: 32px;
      font-weight: 400;
      letter-spacing: 1px;
    }
    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 14px;
      line-height: 20px;
    }
    nav.links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 14px;
      line-height: 20px;
    }
    a {
      color: var(--blue);
      text-decoration: none;
      font-weight: 400;
    }
    main.app {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 12px;
      padding: 16px 0 28px;
      align-items: start;
    }
    .panel, .workbench, .notice {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
    }
    .setup {
      display: grid;
      gap: 10px;
      position: sticky;
      top: 12px;
    }
    .panel {
      padding: 24px;
      display: grid;
      gap: 12px;
    }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 2px;
    }
    .panel-title h2 {
      margin: 0;
      font-size: 20px;
      line-height: 32px;
      font-weight: 400;
      letter-spacing: 1px;
    }
    label, legend {
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      text-transform: none;
    }
    label {
      display: grid;
      gap: 5px;
    }
    input, select, button {
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--field);
      color: var(--ink);
      font: inherit;
      padding: 0 16px;
    }
    button {
      background: var(--green);
      border-color: var(--green);
      color: var(--ink);
      font-weight: 400;
      cursor: pointer;
      white-space: nowrap;
    }
    button:disabled {
      opacity: .65;
      cursor: wait;
    }
    .secondary, .tab, .chip, .copy-btn, .step-btn {
      background: var(--secondary);
      border-color: var(--line);
      color: var(--muted);
    }
    .secondary:hover, .tab:hover, .chip:hover, .copy-btn:hover, .step-btn:hover {
      border-color: var(--green);
    }
    .topic-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }
    .chip {
      min-height: 36px;
      padding: 0 8px;
      text-align: center;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .chip.active {
      border-color: var(--green);
      background: var(--green);
      color: var(--ink);
    }
    fieldset {
      margin: 0;
      padding: 0;
      border: 0;
      display: grid;
      gap: 6px;
    }
    .segment {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--field);
    }
    .segment label {
      min-height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--ink);
      font-size: 13px;
      font-weight: 400;
      text-transform: none;
      border-right: 1px solid var(--line);
      cursor: pointer;
    }
    .segment label:last-child { border-right: 0; }
    .segment input { display: none; }
    .segment label:has(input:checked) {
      background: var(--green);
      color: var(--ink);
    }
    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .stepper {
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr) 38px;
      gap: 6px;
    }
    .stepper input {
      text-align: center;
      padding: 0 4px;
    }
    .step-btn {
      padding: 0;
      font-size: 20px;
    }
    .check {
      min-height: 38px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 400;
      text-transform: none;
      background: var(--field);
    }
    .check input {
      min-height: 0;
      width: auto;
      padding: 0;
    }
    details {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      background: var(--field);
    }
    summary {
      color: var(--muted);
      cursor: pointer;
      font-size: 14px;
      font-weight: 400;
    }
    .advanced-grid {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .notice {
      padding: 12px;
      color: var(--muted);
      font-size: 14px;
      line-height: 20px;
    }
    .workbench {
      min-height: 646px;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      overflow: hidden;
    }
    .status {
      min-height: 52px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .status-text {
      min-width: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 20px;
      overflow-wrap: anywhere;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 9px;
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      white-space: nowrap;
    }
    .pill.ok { background: var(--field); color: var(--blue); }
    .pill.err { background: var(--secondary); color: var(--red); }
    .pill.run { background: var(--secondary); color: var(--blue); }
    .tabs {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border-bottom: 1px solid var(--line);
    }
    .tab {
      min-height: 44px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      font-size: 13px;
    }
    .tab:last-child { border-right: 0; }
    .tab.active {
      box-shadow: inset 0 -3px 0 var(--green);
      color: var(--ink);
      background: var(--field);
    }
    .panel-host {
      min-height: 0;
      padding: 14px;
    }
    .tab-panel {
      display: none;
      min-height: 434px;
    }
    .tab-panel.active {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 10px;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .panel-head h2 {
      margin: 0;
      font-size: 20px;
      line-height: 32px;
      font-weight: 400;
      letter-spacing: 1px;
    }
    .copy-btn {
      width: auto;
      min-height: 32px;
      padding: 0 9px;
      font-size: 13px;
    }
    .content {
      min-height: 320px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      background: var(--field);
      line-height: 1.55;
    }
    .empty {
      color: var(--muted);
    }
    .validation-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: var(--field);
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: none;
      font-weight: 400;
    }
    .metric .value {
      margin-top: 5px;
      font-size: 17px;
      font-weight: 400;
      overflow-wrap: anywhere;
    }
    .checks {
      display: grid;
      gap: 8px;
    }
    .check-row {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: var(--field);
    }
    .check-row .state {
      font-size: 12px;
      font-weight: 400;
      color: var(--muted);
      text-transform: none;
    }
    .check-row.ok .state { color: var(--blue); }
    .check-row.bad .state { color: var(--red); }
    .check-row strong {
      display: block;
      margin-bottom: 4px;
    }
    .check-row p {
      margin: 0;
      color: var(--muted);
      line-height: 1.4;
    }
    .process {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      padding: 12px 14px;
      border-top: 1px solid var(--line);
      background: var(--panel);
    }
    .stage-pill {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 0 9px;
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
    }
    .stage-pill.complete { color: var(--blue); background: var(--field); }
    .stage-pill.warning { color: var(--amber); background: var(--secondary); }
    .stage-pill.error { color: var(--red); background: var(--secondary); }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    @media (max-width: 940px) {
      main.app { grid-template-columns: 1fr; }
      .setup { position: static; }
      .workbench { min-height: 0; }
    }
    @media (max-width: 640px) {
      .wrap { width: min(100vw - 24px, 1180px); }
      .topbar {
        min-height: 0;
        align-items: flex-start;
        flex-direction: column;
        padding: 14px 0;
      }
      main.app { padding-top: 12px; }
      .row, .actions, .topic-grid, .tabs, .validation-grid {
        grid-template-columns: 1fr;
      }
      .tab {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .tab:last-child { border-bottom: 0; }
      .check-row { grid-template-columns: 1fr; }
      .panel-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .copy-btn { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <div>
        <h1>Jikai Practice</h1>
        <div class="subtitle">Singapore tort hypotheticals</div>
      </div>
      <nav class="links" aria-label="demo navigation">
        <a href="/demo/pipeline">Pipeline</a>
        <a href="/health">Health</a>
      </nav>
    </div>
  </header>
  <main class="wrap app">
    <aside class="setup">
      <form class="panel" id="demo-form">
        <div class="panel-title">
          <h2>Question setup</h2>
          <span class="pill">SG Tort</span>
        </div>
        <label>Course
          <select id="jurisdiction">
            <option value="sg">Singapore Tort</option>
          </select>
        </label>
        <fieldset>
          <legend>Topics</legend>
          <div class="topic-grid" id="topic-grid">
            <button class="chip active" type="button" data-topic="negligence">Negligence</button>
            <button class="chip active" type="button" data-topic="causation">Causation</button>
            <button class="chip" type="button" data-topic="duty_of_care">Duty of care</button>
            <button class="chip" type="button" data-topic="remoteness">Remoteness</button>
            <button class="chip" type="button" data-topic="vicarious_liability">Vicarious liability</button>
            <button class="chip" type="button" data-topic="private_nuisance">Private nuisance</button>
          </div>
          <input id="topics" type="hidden" value="negligence, causation">
        </fieldset>
        <label>Subtopics
          <input id="subtopics" value="duty of care, remoteness">
        </label>
        <fieldset>
          <legend>Difficulty</legend>
          <div class="segment">
            <label><input name="complexity" type="radio" value="beginner">Starter</label>
            <label><input name="complexity" type="radio" value="intermediate" checked>Exam</label>
            <label><input name="complexity" type="radio" value="advanced">Hard</label>
          </div>
        </fieldset>
        <div class="row">
          <label>Parties
            <div class="stepper">
              <button class="step-btn" id="party-down" type="button">-</button>
              <input id="parties" type="number" min="2" max="5" value="3">
              <button class="step-btn" id="party-up" type="button">+</button>
            </div>
          </label>
          <label class="check">
            <input id="answer" type="checkbox" checked>
            Model answer
          </label>
        </div>
        <details>
          <summary>Advanced</summary>
          <div class="advanced-grid">
            <label>Provider
              <select id="provider">
                <option value="">Host default</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="ollama">Ollama</option>
                <option value="local">Local</option>
              </select>
            </label>
            <label>Model
              <input id="model" placeholder="host default">
            </label>
          </div>
        </details>
        <div class="actions">
          <button id="submit" type="submit">Generate</button>
          <button class="secondary" id="sample" type="button">Load sample</button>
        </div>
      </form>
      <div class="notice">
        Prompts and outputs are processed by the server-side provider configured by the host. Do not enter personal, privileged, or exam-confidential facts.
      </div>
    </aside>
    <section class="workbench" aria-live="polite">
      <div class="status">
        <div class="status-text" id="status-text">Ready</div>
        <span class="pill" id="status-pill">idle</span>
      </div>
      <div class="tabs" role="tablist" aria-label="generation result">
        <button class="tab active" type="button" data-tab="hypo">Hypothetical</button>
        <button class="tab" type="button" data-tab="answer">Model answer</button>
        <button class="tab" type="button" data-tab="validation">Validation</button>
        <button class="tab" type="button" data-tab="study">Study export</button>
      </div>
      <div class="panel-host">
        <section class="tab-panel active" id="panel-hypo">
          <div class="panel-head">
            <h2>Hypothetical</h2>
            <button class="copy-btn" type="button" data-copy="hypo">Copy</button>
          </div>
          <div class="content empty" id="hypo-text">No hypothetical yet.</div>
        </section>
        <section class="tab-panel" id="panel-answer">
          <div class="panel-head">
            <h2>Model answer</h2>
            <button class="copy-btn" type="button" data-copy="answer">Copy</button>
          </div>
          <div class="content empty" id="answer-text">No model answer yet.</div>
        </section>
        <section class="tab-panel" id="panel-validation">
          <div class="panel-head">
            <h2>Validation</h2>
            <a href="/demo/pipeline">Open trace</a>
          </div>
          <div id="validation-body">
            <div class="content empty">No validation yet.</div>
          </div>
        </section>
        <section class="tab-panel" id="panel-study">
          <div class="panel-head">
            <h2>Study export</h2>
            <div>
              <button class="copy-btn" type="button" data-copy="tsv">Copy TSV</button>
              <button class="copy-btn" id="download" type="button">Download</button>
            </div>
          </div>
          <div class="content empty"><pre id="study-text">No export yet.</pre></div>
        </section>
      </div>
      <div class="process" id="process">
        <span class="stage-pill">input</span>
        <span class="stage-pill">retrieval</span>
        <span class="stage-pill">generation</span>
        <span class="stage-pill">validation</span>
        <span class="stage-pill">study</span>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const state = { hypo: "", answer: "", tsv: "", topics: ["negligence", "causation"] };
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
    const list = (value) => value.split(",").map((item) => item.trim()).filter(Boolean);
    const selectedComplexity = () => document.querySelector("input[name='complexity']:checked").value;

    function setStatus(text, mode) {
      $("status-text").textContent = text;
      $("status-pill").textContent = mode;
      $("status-pill").className = `pill ${mode}`;
    }

    function setText(id, value, emptyText) {
      const el = $(id);
      el.textContent = value || emptyText;
      el.classList.toggle("empty", !value);
    }

    function syncTopics() {
      const topics = [...document.querySelectorAll(".chip.active")].map((chip) => chip.dataset.topic);
      state.topics = topics.length ? topics : ["negligence"];
      $("topics").value = state.topics.join(", ");
    }

    function setTab(tab) {
      document.querySelectorAll(".tab").forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tab);
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `panel-${tab}`);
      });
    }

    function complexityLabel(value) {
      return { beginner: "starter", intermediate: "exam", advanced: "hard" }[value] || value;
    }

    function requestBody() {
      const jurisdiction = $("jurisdiction").value;
      const provider = $("provider").value;
      const model = $("model").value.trim();
      const body = {
        topics: list($("topics").value),
        corpus_pack: jurisdiction === "sg" ? "sg_tort" : `${jurisdiction}_tort`,
        jurisdiction,
        subject: "tort",
        law_domain: "tort",
        subtopics: list($("subtopics").value),
        number_parties: Number($("parties").value),
        complexity_level: selectedComplexity(),
        user_preferences: {
          include_model_answer: $("answer").checked,
          timeout_seconds: 90
        },
        include_analysis: true
      };
      if (provider) body.provider = provider;
      if (model) body.model = model;
      return body;
    }

    function metric(label, value) {
      return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
    }

    function renderValidation(validation) {
      if (!validation || !Object.keys(validation).length) {
        $("validation-body").innerHTML = `<div class="content empty">No validation returned.</div>`;
        return;
      }
      const similarity = validation.similarity_check || {};
      const checks = validation.checks || {};
      const rows = Object.entries(checks).map(([name, check]) => {
        const ok = check && check.passed;
        const label = name.replaceAll("_", " ");
        const message = check && check.message ? check.message : JSON.stringify(check);
        return `
          <div class="check-row ${ok ? "ok" : "bad"}">
            <div class="state">${ok ? "passed" : "review"}</div>
            <div><strong>${esc(label)}</strong><p>${esc(message)}</p></div>
          </div>`;
      }).join("");
      $("validation-body").innerHTML = `
        <div class="validation-grid">
          ${metric("overall", validation.overall_score ?? (validation.passed ? "pass" : "review"))}
          ${metric("realism", validation.legal_realism_score ?? "n/a")}
          ${metric("exam", validation.exam_likeness_score ?? "n/a")}
          ${metric("similarity", similarity.max_similarity ?? "n/a")}
        </div>
        <div class="checks">${rows || `<div class="content empty">No checks returned.</div>`}</div>`;
    }

    function makeTsv(hypo, answer, topics) {
      const tags = topics.map((topic) => `tort::${topic}`).join(" ");
      return `${hypo}\t${answer || "Review the facts and apply duty, breach, causation, remoteness, and defences."}\t${tags}`;
    }

    function renderProcess(stages) {
      if (!Array.isArray(stages) || !stages.length) return;
      $("process").innerHTML = stages.map((stage) => {
        const name = String(stage.id || stage.label || "").replaceAll("_", " ");
        return `<span class="stage-pill ${esc(stage.status || "")}">${esc(name)}</span>`;
      }).join("");
    }

    function renderResult(payload, stages) {
      const topics = payload.topics || state.topics;
      const hypo = payload.hypothetical || payload.output || "";
      const answer = payload.model_answer || "";
      const tsv = payload.anki_tsv_preview || makeTsv(hypo, answer, topics);
      state.hypo = hypo;
      state.answer = answer;
      state.tsv = tsv;
      state.topics = topics;
      setText("hypo-text", hypo, "No hypothetical returned.");
      setText("answer-text", answer, "No model answer returned.");
      $("study-text").textContent = tsv || "No export returned.";
      $("study-text").parentElement.classList.toggle("empty", !tsv);
      renderValidation(payload.validation_results || {});
      renderProcess(stages);
      setTab("hypo");
    }

    function normalizeTrace(trace) {
      const stages = trace.stages || [];
      const byId = Object.fromEntries(stages.map((stage) => [stage.id, stage]));
      const generation = (byId.generation && byId.generation.details) || {};
      const validation = (byId.validation && byId.validation.details) || generation.validation_results || {};
      const study = (byId.study && byId.study.details) || {};
      return {
        payload: {
          hypothetical: generation.output || "",
          model_answer: generation.model_answer || study.model_answer || "",
          validation_results: validation,
          anki_tsv_preview: study.anki_tsv_preview || "",
          topics: (trace.summary && trace.summary.topics) || state.topics
        },
        stages
      };
    }

    function renderError(status, payload) {
      const detail = payload.detail || payload;
      const message = detail.message || detail.code || JSON.stringify(detail);
      setText("hypo-text", `Generation failed: ${message}`, "");
      setText("answer-text", "", "No model answer returned.");
      $("validation-body").innerHTML = `<div class="content"><pre>${esc(JSON.stringify({status, detail}, null, 2))}</pre></div>`;
      setTab("hypo");
    }

    async function safeJson(res) {
      try {
        return await res.json();
      } catch {
        return { detail: await res.text() };
      }
    }

    async function generate(event) {
      event.preventDefault();
      syncTopics();
      setStatus(`Generating ${complexityLabel(selectedComplexity())} question`, "run");
      $("submit").disabled = true;
      $("sample").disabled = true;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 95000);
      try {
        const res = await fetch("/workflow/generate", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(requestBody()),
          signal: controller.signal
        });
        const payload = await safeJson(res);
        if (!res.ok) {
          setStatus("Generation failed", "err");
          renderError(res.status, payload);
          return;
        }
        setStatus("Generated", "ok");
        renderResult(payload, []);
      } catch (error) {
        setStatus("Generation failed", "err");
        renderError(0, {
          detail: {
            code: error.name === "AbortError" ? "client_timeout" : "request_failed",
            message: error.name === "AbortError" ? "Request timed out in the browser." : error.message
          }
        });
      } finally {
        clearTimeout(timer);
        $("submit").disabled = false;
        $("sample").disabled = false;
      }
    }

    async function loadSample() {
      syncTopics();
      setStatus("Loading sample trace", "run");
      $("submit").disabled = true;
      $("sample").disabled = true;
      try {
        const params = new URLSearchParams({ topics: state.topics.join(",") });
        const res = await fetch(`/demo/pipeline/trace?${params.toString()}`);
        const payload = await safeJson(res);
        if (!res.ok) {
          setStatus("Sample failed", "err");
          renderError(res.status, payload);
          return;
        }
        const result = normalizeTrace(payload);
        setStatus("Sample loaded", "ok");
        renderResult(result.payload, result.stages);
      } catch (error) {
        setStatus("Sample failed", "err");
        renderError(0, { detail: { code: "sample_failed", message: error.message } });
      } finally {
        $("submit").disabled = false;
        $("sample").disabled = false;
      }
    }

    async function copyText(value) {
      if (!value) return;
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const area = document.createElement("textarea");
      area.value = value;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }

    function downloadTsv() {
      if (!state.tsv) return;
      const blob = new Blob([state.tsv], { type: "text/tab-separated-values;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "jikai-study.tsv";
      link.click();
      URL.revokeObjectURL(link.href);
    }

    document.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        chip.classList.toggle("active");
        syncTopics();
      });
    });
    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", () => setTab(button.dataset.tab));
    });
    document.querySelectorAll("[data-copy]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.copy;
        copyText(key === "hypo" ? state.hypo : key === "answer" ? state.answer : state.tsv);
      });
    });
    $("party-down").addEventListener("click", () => {
      $("parties").value = Math.max(2, Number($("parties").value) - 1);
    });
    $("party-up").addEventListener("click", () => {
      $("parties").value = Math.min(5, Number($("parties").value) + 1);
    });
    $("download").addEventListener("click", downloadTsv);
    $("sample").addEventListener("click", loadSample);
    $("demo-form").addEventListener("submit", generate);
    syncTopics();
  </script>
</body>
</html>
"""
