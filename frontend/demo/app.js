const $ = (id) => document.getElementById(id);
const state = { runId: 0, topics: ["negligence", "causation"], db: null };
const DB_NAME = "jikai-demo";
const DB_VERSION = 1;
const RUN_STORE = "runs";
const META_STORE = "meta";

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;"
}[ch]));

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(RUN_STORE)) {
        const runs = db.createObjectStore(RUN_STORE, { keyPath: "id" });
        runs.createIndex("createdAt", "createdAt");
        runs.createIndex("status", "status");
      }
      if (!db.objectStoreNames.contains(META_STORE)) {
        db.createObjectStore(META_STORE, { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(store, mode = "readonly") {
  return state.db.transaction(store, mode).objectStore(store);
}

function idbGet(store, key) {
  return new Promise((resolve, reject) => {
    const req = tx(store).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbPut(store, value) {
  return new Promise((resolve, reject) => {
    const req = tx(store, "readwrite").put(value);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbAll(store) {
  return new Promise((resolve, reject) => {
    const req = tx(store).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function pack(value) {
  const raw = new TextEncoder().encode(JSON.stringify(value));
  if (!("CompressionStream" in window)) {
    return { data: raw.buffer, compressed: false, encoding: "json" };
  }
  const stream = new Blob([raw]).stream().pipeThrough(new CompressionStream("gzip"));
  const data = await new Response(stream).arrayBuffer();
  return { data, compressed: true, encoding: "gzip" };
}

async function unpack(record) {
  if (!record || !record.data) return {};
  let buffer = record.data;
  if (record.compressed && "DecompressionStream" in window) {
    const stream = new Blob([buffer]).stream().pipeThrough(new DecompressionStream("gzip"));
    buffer = await new Response(stream).arrayBuffer();
  }
  return JSON.parse(new TextDecoder().decode(buffer));
}

async function saveRun(snapshot) {
  const payload = await pack(snapshot);
  await idbPut(RUN_STORE, {
    id: snapshot.id,
    createdAt: snapshot.createdAt,
    title: snapshot.title,
    status: snapshot.status,
    mode: snapshot.mode,
    topics: snapshot.topics || [],
    data: payload.data,
    compressed: payload.compressed,
    encoding: payload.encoding
  });
  await renderHistory();
}

async function readRun(id) {
  const record = await idbGet(RUN_STORE, id);
  if (!record) return null;
  return unpack(record);
}

async function showStorageNotice() {
  const accepted = await idbGet(META_STORE, "storage_notice_accepted");
  if (accepted && accepted.value) {
    $("storage-modal").classList.add("hidden");
    return;
  }
  $("storage-modal").classList.remove("hidden");
}

function setActiveSurface(surface) {
  state.surface = surface;
}

function showConversation(clear = false, showComposer = true) {
  $("hero").classList.add("hidden");
  $("conversation").classList.remove("hidden");
  $("chat-form").hidden = !showComposer;
  if (clear) $("messages").innerHTML = "";
}

function showHero() {
  setActiveSurface("practice");
  $("messages").innerHTML = "";
  $("conversation").classList.add("hidden");
  $("hero").classList.remove("hidden");
}

function addUserMessage(prompt) {
  $("messages").insertAdjacentHTML("beforeend", `
    <article class="message user">
      <div class="bubble">${esc(prompt)}</div>
    </article>`);
}

function topicsFromPrompt(prompt) {
  const lower = prompt.toLowerCase();
  const topics = [];
  [
    ["negligence", "negligence"],
    ["causation", "causation"],
    ["duty", "duty_of_care"],
    ["remoteness", "remoteness"],
    ["vicarious", "vicarious_liability"],
    ["nuisance", "private_nuisance"]
  ].forEach(([needle, topic]) => {
    if (lower.includes(needle) && !topics.includes(topic)) topics.push(topic);
  });
  return topics.length ? topics : ["negligence", "causation"];
}

function subtopicsFromPrompt(prompt) {
  const lower = prompt.toLowerCase();
  const subtopics = [];
  if (lower.includes("duty")) subtopics.push("duty_of_care");
  if (lower.includes("remoteness")) subtopics.push("remoteness");
  return subtopics.length ? subtopics : ["duty_of_care", "remoteness"];
}

function requestBody(prompt) {
  const topics = topicsFromPrompt(prompt);
  state.topics = topics;
  return {
    topics,
    corpus_pack: "sg_tort",
    jurisdiction: "sg",
    subject: "tort",
    law_domain: "tort",
    subtopics: subtopicsFromPrompt(prompt),
    number_parties: 3,
    complexity_level: prompt.toLowerCase().includes("hard") ? "advanced" : "intermediate",
    user_preferences: {
      include_model_answer: true,
      timeout_seconds: 90
    },
    include_analysis: true
  };
}

function stationLabel(stage) {
  const labels = {
    input: "Input",
    classification: "Classify",
    scoring: "Score",
    planning: "Plan",
    retrieval: "Pull cases",
    prompt: "Assemble",
    generation: "Draft",
    validation: "Validate",
    study: "Export"
  };
  return labels[stage.id] || stage.label || stage.id;
}

function stageSet(stages) {
  const display = (stages || []).filter((stage) =>
    ["input", "classification", "retrieval", "prompt", "generation", "validation"].includes(stage.id)
  );
  return display.length ? display : [
    { id: "input", status: "complete" },
    { id: "classification", status: "running" },
    { id: "retrieval", status: "pending" },
    { id: "prompt", status: "pending" },
    { id: "generation", status: "pending" },
    { id: "validation", status: "pending" }
  ];
}

function traceSteps(stages) {
  return stageSet(stages).map((stage) => `
    <div class="trace-step ${esc(stage.status || "pending")}">
      <div class="trace-step-dot"></div>
      <strong>${esc(stationLabel(stage))}</strong>
      <span>${esc(stage.status || "pending")}</span>
    </div>`).join("");
}

function factoryMarkup(stages, items) {
  const display = stageSet(stages);
  const crates = (items && items.length ? items : [
    { case_name: "corpus", topics: ["queued"] },
    { case_name: "facts", topics: ["routing"] },
    { case_name: "answer", topics: ["validation"] }
  ]).slice(0, 3);
  return `
    <div class="factory-line" aria-label="Animated case retrieval pipeline">
      <div class="factory-belt">
        ${crates.map((item, index) => `
          <div class="case-crate crate-${index + 1}">
            <strong>${esc(item.case_name || item.id || `case ${index + 1}`)}</strong>
            <span>${esc(((item.topics || [])[0]) || "case")}</span>
          </div>`).join("")}
      </div>
      <div class="factory-stations">
        ${display.map((stage) => `
          <div class="factory-station ${esc(stage.status || "pending")}">
            <span></span>
            <strong>${esc(stationLabel(stage))}</strong>
          </div>`).join("")}
      </div>
    </div>`;
}

function caseMarkup(items) {
  if (!items || !items.length) {
    return `
      <div class="case-card"><strong>Waiting for corpus</strong><p>Jikai is ranking SG Tort examples by topic overlap.</p></div>
      <div class="case-card"><strong>Retrieval queued</strong><p>Retrieved cases will appear in this chat run.</p></div>
      <div class="case-card"><strong>Validation queued</strong><p>The output will be checked for coverage and similarity.</p></div>`;
  }
  return items.slice(0, 3).map((item) => `
    <div class="case-card">
      <strong>${esc(item.case_name || item.id || "Corpus item")}</strong>
      <div class="tag-row">${(item.topics || []).slice(0, 3).map((topic) => `<span class="tag">${esc(topic)}</span>`).join("")}</div>
      <p>${esc(item.excerpt || "Corpus excerpt unavailable.")}</p>
    </div>`).join("");
}

function detailMarkup(stages) {
  if (!stages || !stages.length) {
    return "";
  }
  return `
    <details class="trace-details">
      <summary>Trace details</summary>
      ${stages.map((stage) => `
        <div class="stage-detail">
          <strong><span>${esc(stage.label || stationLabel(stage))}</span><span>${esc(stage.status || "")}</span></strong>
          <pre>${esc(JSON.stringify(stage.details || {}, null, 2))}</pre>
        </div>`).join("")}
    </details>`;
}

function traceMarkup(trace, active = true) {
  const stages = (trace && trace.stages) || [];
  const retrieval = stages.find((stage) => stage.id === "retrieval");
  const cases = retrieval && retrieval.details ? retrieval.details.items : [];
  return `
    <div class="trace-panel ${active ? "is-running" : "is-done"}">
      ${factoryMarkup(stages, cases)}
      <div class="trace-stages">${traceSteps(stages)}</div>
      <div class="case-grid">${caseMarkup(cases)}</div>
      ${detailMarkup(stages)}
    </div>`;
}

function thinkingCard(runId) {
  return `
    <article class="message" id="run-${runId}">
      <div class="assistant-card">
        <div class="assistant-head">
          <div class="assistant-title">
            <strong>Thinking through the pipeline</strong>
            <span>Classifier, retriever, prompt builder, generator, validator</span>
          </div>
          <span class="status-pill">running</span>
        </div>
        <div class="trace-host">${traceMarkup(null)}</div>
      </div>
    </article>`;
}

function updateThinking(runId, trace) {
  const host = document.getElementById(`run-${runId}`);
  if (!host) return;
  const traceHost = host.querySelector(".trace-host");
  if (traceHost) traceHost.innerHTML = traceMarkup(trace, true);
}

function normalizeTrace(trace) {
  const stages = trace.stages || [];
  const byId = Object.fromEntries(stages.map((stage) => [stage.id, stage]));
  const generation = (byId.generation && byId.generation.details) || {};
  const validation = (byId.validation && byId.validation.details) || {};
  const study = (byId.study && byId.study.details) || {};
  return {
    hypothetical: generation.output || "",
    model_answer: generation.model_answer || study.model_answer || "",
    validation_results: validation,
    anki_tsv_preview: study.anki_tsv_preview || "",
    topics: (trace.summary && trace.summary.topics) || state.topics,
    stages
  };
}

function metric(label, value) {
  return `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
}

function answerMarkup(payload, traceMode) {
  const validation = payload.validation_results || {};
  const similarity = validation.similarity_check || {};
  const topics = payload.topics || state.topics;
  return `
    <div class="answer-grid">
      <div class="answer-block">
        <h2>Hypothetical</h2>
        <p class="answer-text">${esc(payload.hypothetical || "No hypothetical returned.")}</p>
      </div>
      <div class="answer-block">
        <h2>Model answer</h2>
        <p class="answer-text">${esc(payload.model_answer || "No model answer returned.")}</p>
      </div>
      <div class="metric-grid">
        ${metric("mode", traceMode)}
        ${metric("topics", topics.join(", "))}
        ${metric("score", validation.overall_score ?? validation.quality_score ?? "n/a")}
        ${metric("similarity", similarity.max_similarity ?? "n/a")}
      </div>
    </div>`;
}

function setRunStatus(runId, label, isError = false) {
  const host = document.getElementById(`run-${runId}`);
  if (!host) return;
  const pill = host.querySelector(".status-pill");
  if (!pill) return;
  pill.textContent = label;
  pill.classList.toggle("error", isError);
  host.querySelectorAll(".trace-panel").forEach((panel) => {
    panel.classList.toggle("is-running", label === "running");
    panel.classList.toggle("is-done", label !== "running");
  });
}

function completeRun(runId, payload, traceMode) {
  const host = document.getElementById(`run-${runId}`);
  if (!host) return;
  setRunStatus(runId, "complete");
  host.querySelector(".assistant-card").insertAdjacentHTML("beforeend", answerMarkup(payload, traceMode));
}

function failRun(runId, payload) {
  const host = document.getElementById(`run-${runId}`);
  if (!host) return;
  const detail = payload.detail || payload;
  const message = detail.message || detail.code || JSON.stringify(detail);
  setRunStatus(runId, "failed", true);
  host.querySelector(".assistant-card").insertAdjacentHTML("beforeend", `
    <div class="error-box">
      <strong>Generation failed</strong>
      <p>${esc(message)}</p>
      <p>Use Load sample to inspect a local trace without a live provider.</p>
    </div>`);
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return { detail: await res.text() };
  }
}

async function fetchTrace(prompt) {
  const body = requestBody(prompt);
  const params = new URLSearchParams({ topics: body.topics.join(",") });
  const res = await fetch(`/demo/pipeline/trace?${params.toString()}`);
  const payload = await safeJson(res);
  if (!res.ok) throw payload;
  return payload;
}

function runTitle(prompt, mode) {
  const title = prompt.replace(/\s+/g, " ").trim().slice(0, 58);
  return title || `${mode} run`;
}

function promptFrom(activeId) {
  const value = $(activeId).value.trim();
  return value || "Generate an exam-style SG tort hypothetical on negligence and causation.";
}

function runSnapshot({ id, prompt, status, mode, trace, payload, error }) {
  return {
    id,
    createdAt: new Date().toISOString(),
    title: runTitle(prompt, mode),
    status,
    mode,
    prompt,
    topics: state.topics,
    trace,
    payload,
    error
  };
}

async function runSample(prompt) {
  const runId = `run-${Date.now()}-${++state.runId}`;
  setActiveSurface("practice");
  showConversation();
  addUserMessage(prompt);
  $("messages").insertAdjacentHTML("beforeend", thinkingCard(runId));
  const trace = await fetchTrace(prompt);
  updateThinking(runId, trace);
  const payload = normalizeTrace(trace);
  completeRun(runId, payload, "sample");
  $("chat-prompt").value = "";
  document.getElementById(`run-${runId}`).scrollIntoView({ block: "start", behavior: "smooth" });
}

async function runGenerate(prompt) {
  const runId = `run-${Date.now()}-${++state.runId}`;
  let trace = null;
  setActiveSurface("practice");
  showConversation();
  addUserMessage(prompt);
  $("messages").insertAdjacentHTML("beforeend", thinkingCard(runId));
  const tracePromise = fetchTrace(prompt).then((nextTrace) => {
    trace = nextTrace;
    updateThinking(runId, nextTrace);
    return nextTrace;
  }).catch(() => null);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 95000);
  try {
    const res = await fetch("/workflow/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(requestBody(prompt)),
      signal: controller.signal
    });
    const payload = await safeJson(res);
    if (!res.ok) {
      await tracePromise;
      failRun(runId, payload);
      await saveRun(runSnapshot({ id: runId, prompt, status: "failed", mode: "live", trace, error: payload }));
      return;
    }
    await tracePromise;
    completeRun(runId, payload, "live");
    await saveRun(runSnapshot({ id: runId, prompt, status: "complete", mode: "live", trace, payload }));
  } catch (error) {
    const payload = {
      detail: {
        code: error.name === "AbortError" ? "client_timeout" : "request_failed",
        message: error.name === "AbortError" ? "Request timed out in the browser." : error.message
      }
    };
    await tracePromise;
    failRun(runId, payload);
    await saveRun(runSnapshot({ id: runId, prompt, status: "failed", mode: "live", trace, error: payload }));
  } finally {
    clearTimeout(timer);
  }
}

async function renderHistory() {
  const list = $("history-list");
  const records = (await idbAll(RUN_STORE))
    .filter((record) => record.mode === "live")
    .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
    .slice(0, 30);
  if (!records.length) {
    list.innerHTML = `<div class="history-empty">No saved runs yet.</div>`;
    return;
  }
  list.innerHTML = records.map((record) => `
    <button class="history-link" type="button" data-run-id="${esc(record.id)}">
      <strong>${esc(record.title || record.mode || "saved run")}</strong>
      <span>${esc(record.status)} | ${esc(record.mode)} | ${esc(new Date(record.createdAt).toLocaleString())}</span>
    </button>`).join("");
  list.querySelectorAll("[data-run-id]").forEach((button) => {
    button.addEventListener("click", () => openSavedRun(button.dataset.runId));
  });
}

function savedRunMarkup(run) {
  if (run.mode === "health") {
    return healthMarkup(run.payload, run.incidents || []);
  }
  return `
    <article class="message">
      <div class="assistant-card">
        <div class="assistant-head">
          <div class="assistant-title">
            <strong>${run.status === "failed" ? "Saved failed run" : "Saved run"}</strong>
            <span>${esc(new Date(run.createdAt).toLocaleString())}</span>
          </div>
          <span class="status-pill ${run.status === "failed" ? "error" : ""}">${esc(run.status)}</span>
        </div>
        ${run.trace ? traceMarkup(run.trace, false) : ""}
        ${run.payload ? answerMarkup(run.payload, run.mode) : ""}
        ${run.error ? `<div class="error-box"><strong>Generation failed</strong><p>${esc((run.error.detail && (run.error.detail.message || run.error.detail.code)) || JSON.stringify(run.error))}</p></div>` : ""}
      </div>
    </article>`;
}

async function openSavedRun(id) {
  const run = await readRun(id);
  if (!run) return;
  setActiveSurface("practice");
  showConversation(true, false);
  if (run.prompt) addUserMessage(run.prompt);
  $("messages").insertAdjacentHTML("beforeend", savedRunMarkup(run));
}

function component(name, ok, detail) {
  const status = ok ? "Operational" : "Degraded";
  return `
    <div class="status-component">
      <div>
        <strong>${esc(name)}</strong><br>
        <small>${esc(detail || "Runtime check")}</small>
      </div>
      <div><span class="status-dot ${ok ? "" : "degraded"}"></span> ${status}</div>
    </div>`;
}

function llmComponent(llm) {
  if (!llm || !Object.keys(llm).length) {
    return component("LLM provider", false, "No provider health returned");
  }
  const values = Object.values(llm);
  const ok = values.some((entry) => entry === true || (entry && entry.healthy === true) || (entry && entry.status === "healthy"));
  return component("LLM provider", ok, "Configured provider availability");
}

function incidentMarkup(incidents) {
  const failed = (incidents || []).filter((run) => run.status === "failed").slice(0, 5);
  if (!failed.length) {
    return `<div class="incident"><strong>No local incidents recorded.</strong><span>Failed browser runs will appear here.</span></div>`;
  }
  return failed.map((run) => `
    <div class="incident">
      <strong>${esc(run.title || "Failed run")}</strong>
      <span>${esc(new Date(run.createdAt).toLocaleString())} | ${esc(run.mode || "run")}</span>
    </div>`).join("");
}

function healthMarkup(payload, incidents) {
  const services = (payload && payload.services) || {};
  const dbOk = services.database === true;
  const corpusOk = services.corpus && services.corpus.healthy !== false;
  const allOk = payload && payload.status === "healthy";
  return `
    <article class="message">
      <div class="assistant-card">
        <div class="assistant-head">
          <div class="assistant-title">
            <strong>Jikai Status</strong>
            <span>Local runtime status, rendered from /health</span>
          </div>
          <span class="status-pill ${allOk ? "" : "error"}">${esc(payload?.status || "unknown")}</span>
        </div>
        <div class="status-page">
          <div class="status-banner ${allOk ? "operational" : "degraded"}">
            <div>
              <strong>${allOk ? "Core Local Systems Operational" : "Some Local Systems Degraded"}</strong>
              <div class="fine-print">Last checked ${esc(new Date().toLocaleString())}. Uptime is not tracked locally.</div>
            </div>
            <div>version ${esc(payload?.version || "unknown")}</div>
          </div>
          <div class="status-components">
            ${component("API", true, "Browser reached the FastAPI process")}
            ${component("Database", dbOk, "Generation history and reports")}
            ${component("Corpus", corpusOk, `${services.corpus?.total_entries ?? "n/a"} entries indexed`)}
            ${llmComponent(services.llm)}
          </div>
          <div>
            <h2>Past local incidents</h2>
            <div class="incident-list">${incidentMarkup(incidents)}</div>
          </div>
        </div>
      </div>
    </article>`;
}

async function showHealth() {
  setActiveSurface("health");
  showConversation(true);
  addUserMessage("Show Jikai runtime health.");
  const res = await fetch("/health");
  const payload = await safeJson(res);
  const records = (await idbAll(RUN_STORE)).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  const incidents = records.filter((record) => record.status === "failed");
  $("messages").insertAdjacentHTML("beforeend", healthMarkup(payload, incidents));
}

function bindEvents() {
  $("hero-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runGenerate(promptFrom("prompt"));
  });
  $("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runGenerate(promptFrom("chat-prompt"));
  });
  $("sample").addEventListener("click", () => runSample(promptFrom("prompt")));
  $("chat-sample").addEventListener("click", () => runSample(promptFrom("chat-prompt")));
  $("new-run").addEventListener("click", showHero);
  $("top-status").addEventListener("click", showHealth);
  $("clear-prompt").addEventListener("click", () => {
    $("prompt").value = "";
    $("prompt").focus();
  });
  $("storage-accept").addEventListener("click", async () => {
    await idbPut(META_STORE, { key: "storage_notice_accepted", value: true, acceptedAt: new Date().toISOString() });
    $("storage-modal").classList.add("hidden");
  });
}

async function init() {
  state.db = await openDb();
  bindEvents();
  await showStorageNotice();
  await renderHistory();
}

init().catch((error) => {
  console.error(error);
  $("storage-modal").classList.add("hidden");
});
