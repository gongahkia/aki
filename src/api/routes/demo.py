"""Demo surfaces for launch and README artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ...services.hypothetical_service import GenerationRequest
from ...services.pipeline_trace_service import (
    default_pipeline_trace_request,
    pipeline_trace_service,
)

router = APIRouter()


class PipelineTraceRequest(BaseModel):
    topics: List[str] = Field(default_factory=lambda: ["negligence", "causation"])
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    law_domain: str = "tort"
    number_parties: int = Field(default=3, ge=2, le=5)
    complexity_level: str = "intermediate"
    sample_size: int = Field(default=3, ge=1, le=10)
    user_preferences: Optional[Dict[str, Any]] = None
    live: bool = False
    expose_prompt: bool = False
    expose_provider: bool = False


PIPELINE_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Jikai Pipeline Trace</title>
  <style>
    :root {
      --bg: #f5f7f4;
      --ink: #17211b;
      --muted: #58645d;
      --line: #cbd6cf;
      --panel: #ffffff;
      --green: #0f7a4f;
      --blue: #245f9f;
      --amber: #9d6200;
      --red: #a7332e;
      --soft: #e9efe9;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .wrap {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }
    .topbar {
      min-height: 72px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      font-size: 24px;
      line-height: 1.15;
      margin: 0;
      letter-spacing: 0;
    }
    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
      align-items: center;
    }
    input, select, button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      min-height: 36px;
    }
    input[type="text"] {
      width: min(320px, 52vw);
      padding: 0 10px;
    }
    label.toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 36px;
      padding: 0 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
    }
    button {
      padding: 0 12px;
      background: var(--green);
      border-color: var(--green);
      color: #fff;
      font-weight: 650;
      cursor: pointer;
    }
    main { padding: 20px 0 28px; }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric, .stage {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .metric {
      min-height: 72px;
      padding: 12px;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    .metric .value {
      margin-top: 6px;
      font-size: 18px;
      font-weight: 750;
      overflow-wrap: anywhere;
    }
    .grid {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .rail {
      position: sticky;
      top: 12px;
      display: grid;
      gap: 8px;
    }
    .rail button {
      width: 100%;
      min-height: 44px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #fff;
      color: var(--ink);
      border-color: var(--line);
      font-weight: 650;
      text-align: left;
    }
    .rail button.active {
      border-color: var(--green);
      box-shadow: inset 4px 0 0 var(--green);
    }
    .badge {
      display: inline-block;
      min-width: 76px;
      padding: 3px 8px;
      border-radius: 999px;
      text-align: center;
      font-size: 12px;
      font-weight: 750;
      background: var(--soft);
      color: var(--muted);
    }
    .badge.complete { background: #dff3e8; color: var(--green); }
    .badge.warning { background: #fff1d4; color: var(--amber); }
    .badge.error { background: #ffe2df; color: var(--red); }
    .stage {
      display: none;
      min-height: 560px;
      padding: 18px;
    }
    .stage.active { display: block; }
    .stage h2 {
      margin: 0 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 12px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #f8faf8;
      max-height: 460px;
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
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfb;
    }
    .item strong { display: block; margin-bottom: 4px; }
    .item p { margin: 6px 0 0; color: var(--muted); line-height: 1.45; }
    .failures {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }
    .failure {
      border: 1px solid #efb8b3;
      color: var(--red);
      background: #fff7f6;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      font-weight: 700;
    }
    @media (max-width: 800px) {
      .topbar { align-items: flex-start; flex-direction: column; padding: 14px 0; }
      .controls { justify-content: flex-start; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid { grid-template-columns: 1fr; }
      .rail { position: static; }
      .stage { min-height: 0; }
      input[type="text"] { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <div>
        <h1>Jikai Pipeline Trace</h1>
        <div class="subtitle" id="trace-mode">fixture trace</div>
      </div>
      <div class="controls">
        <input id="topics" type="text" value="negligence, causation" aria-label="topics">
        <label class="toggle"><input id="live" type="checkbox"> live</label>
        <label class="toggle"><input id="prompt" type="checkbox"> prompt</label>
        <label class="toggle"><input id="provider" type="checkbox"> provider</label>
        <button id="run" type="button">Run trace</button>
      </div>
    </div>
  </header>
  <main class="wrap">
    <section class="summary" id="summary"></section>
    <section class="grid">
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
      const topics = $("topics").value.split(",").map((v) => v.trim()).filter(Boolean);
      const params = new URLSearchParams({
        topics: topics.join(","),
        live: $("live").checked ? "true" : "false",
        expose_prompt: $("prompt").checked ? "true" : "false",
        expose_provider: $("provider").checked ? "true" : "false"
      });
      const res = await fetch(`/demo/pipeline/trace?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      render(await res.json());
    }

    $("run").addEventListener("click", () => loadTrace().catch((err) => {
      $("stage-host").innerHTML = `<section class="stage active"><h2>Error</h2><pre>${esc(err.message)}</pre></section>`;
    }));
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
  <title>Jikai Demo</title>
  <style>
    :root {
      --bg: #f7f8f5;
      --ink: #18211c;
      --muted: #5d665f;
      --line: #cfd8d1;
      --panel: #fff;
      --green: #0c754c;
      --blue: #255c91;
      --red: #a7342f;
      --soft: #edf2ed;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      background: #fff;
      border-bottom: 1px solid var(--line);
    }
    .wrap {
      width: min(1160px, calc(100vw - 32px));
      margin: 0 auto;
    }
    .topbar {
      min-height: 72px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    main {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 14px;
      padding: 18px 0 28px;
      align-items: start;
    }
    form, .output, .notice {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    form {
      padding: 14px;
      display: grid;
      gap: 10px;
      position: sticky;
      top: 12px;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    input, select, button, textarea {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      padding: 0 10px;
    }
    textarea {
      min-height: 70px;
      padding-top: 8px;
      resize: vertical;
    }
    button {
      background: var(--green);
      border-color: var(--green);
      color: #fff;
      font-weight: 750;
      cursor: pointer;
    }
    button:disabled {
      opacity: .65;
      cursor: wait;
    }
    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 36px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--muted);
      font-size: 13px;
      text-transform: none;
    }
    .check input { width: auto; min-height: 0; }
    .stack {
      display: grid;
      gap: 10px;
    }
    .notice {
      padding: 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .notice strong { color: var(--ink); }
    .output {
      min-height: 640px;
      padding: 16px;
    }
    .status {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .pill {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      font-weight: 750;
    }
    .pill.ok { background: #dff3e8; color: var(--green); }
    .pill.err { background: #ffe1de; color: var(--red); }
    h2 {
      margin: 0 0 8px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .section {
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }
    .section:first-of-type { border-top: 0; }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9faf8;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .bodytext {
      white-space: pre-wrap;
      line-height: 1.5;
    }
    .links {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    a {
      color: var(--blue);
      text-decoration: none;
      font-weight: 700;
    }
    @media (max-width: 840px) {
      .topbar { align-items: flex-start; flex-direction: column; padding: 14px 0; }
      main { grid-template-columns: 1fr; }
      form { position: static; }
      .row { grid-template-columns: 1fr; }
      .output { min-height: 0; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <div>
        <h1>Jikai Demo</h1>
        <div class="subtitle">SG Tort hypothetical generation</div>
      </div>
      <div class="links">
        <a href="/demo/pipeline">Pipeline trace</a>
        <a href="/health">Health</a>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="stack">
      <form id="demo-form">
        <label>Jurisdiction
          <select id="jurisdiction">
            <option value="sg">Singapore</option>
            <option value="uk">UK</option>
            <option value="us">US</option>
          </select>
        </label>
        <label>Topics
          <input id="topics" value="negligence, causation">
        </label>
        <label>Subtopics
          <input id="subtopics" value="duty of care, remoteness">
        </label>
        <div class="row">
          <label>Complexity
            <select id="complexity">
              <option value="intermediate">Intermediate</option>
              <option value="beginner">Beginner</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
          <label>Parties
            <input id="parties" type="number" min="2" max="5" value="3">
          </label>
        </div>
        <div class="row">
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
        <label class="check">
          <input id="answer" type="checkbox" checked>
          Include model answer
        </label>
        <button id="submit" type="submit">Generate</button>
      </form>
      <div class="notice">
        <strong>Demo mode:</strong> prompts and outputs are processed by the
        server-side provider configured by the host. Do not enter personal data,
        privileged facts, or exam-confidential material.
      </div>
      <div class="notice">
        The public deployment should use server-owned provider credentials,
        request timeouts, and rate limits. Visitors never supply API keys.
      </div>
    </div>
    <section class="output">
      <div class="status">
        <span id="status-text">Ready</span>
        <span id="status-pill" class="pill">idle</span>
      </div>
      <div id="result">
        <div class="section">
          <h2>Result</h2>
          <div class="bodytext">Choose topics and generate an SG Tort hypothetical.</div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
    const list = (value) => value.split(",").map((item) => item.trim()).filter(Boolean);

    function setStatus(text, mode) {
      $("status-text").textContent = text;
      $("status-pill").textContent = mode;
      $("status-pill").className = `pill ${mode === "ok" ? "ok" : mode === "err" ? "err" : ""}`;
    }

    function renderResult(payload) {
      const validation = payload.validation_results || {};
      $("result").innerHTML = `
        <div class="section">
          <h2>Hypothetical</h2>
          <div class="bodytext">${esc(payload.hypothetical || "")}</div>
        </div>
        <div class="section">
          <h2>Model Answer</h2>
          <div class="bodytext">${esc(payload.model_answer || "Not returned.")}</div>
        </div>
        <div class="section">
          <h2>Validation</h2>
          <pre>${esc(JSON.stringify(validation, null, 2))}</pre>
        </div>`;
    }

    function renderError(status, payload) {
      const detail = payload.detail || payload;
      const message = detail.message || detail.code || JSON.stringify(detail);
      $("result").innerHTML = `
        <div class="section">
          <h2>Generation Failed</h2>
          <div class="bodytext">${esc(message)}</div>
        </div>
        <div class="section">
          <h2>Details</h2>
          <pre>${esc(JSON.stringify({status, detail}, null, 2))}</pre>
        </div>`;
    }

    async function generate(event) {
      event.preventDefault();
      setStatus("Generating", "run");
      $("submit").disabled = true;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 95000);
      const jurisdiction = $("jurisdiction").value;
      const body = {
        topics: list($("topics").value),
        corpus_pack: `${jurisdiction}_tort`,
        jurisdiction,
        subject: "tort",
        law_domain: "tort",
        subtopics: list($("subtopics").value),
        number_parties: Number($("parties").value),
        complexity_level: $("complexity").value,
        user_preferences: {
          include_model_answer: $("answer").checked,
          timeout_seconds: 90
        },
        include_analysis: true
      };
      if (jurisdiction === "sg") body.corpus_pack = "sg_tort";
      if ($("provider").value) body.provider = $("provider").value;
      if ($("model").value.trim()) body.model = $("model").value.trim();

      try {
        const res = await fetch("/workflow/generate", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(body),
          signal: controller.signal
        });
        const payload = await res.json();
        if (!res.ok) {
          setStatus("Failed", "err");
          renderError(res.status, payload);
          return;
        }
        setStatus("Complete", "ok");
        renderResult(payload);
      } catch (error) {
        setStatus("Failed", "err");
        renderError(0, {
          detail: {
            code: error.name === "AbortError" ? "client_timeout" : "request_failed",
            message: error.name === "AbortError"
              ? "Request timed out in the browser."
              : error.message
          }
        });
      } finally {
        clearTimeout(timer);
        $("submit").disabled = false;
      }
    }

    $("demo-form").addEventListener("submit", generate);
  </script>
</body>
</html>
"""


def _topics_from_query(raw_topics: str) -> List[str]:
    return [topic.strip() for topic in raw_topics.split(",") if topic.strip()]


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page() -> HTMLResponse:
    return HTMLResponse(PIPELINE_PAGE_HTML)


@router.get("", response_class=HTMLResponse)
async def generation_page() -> HTMLResponse:
    return HTMLResponse(GENERATION_PAGE_HTML)


@router.get("/generate", response_class=HTMLResponse)
async def generation_page_alias() -> HTMLResponse:
    return HTMLResponse(GENERATION_PAGE_HTML)


@router.get("/pipeline/trace")
async def pipeline_trace(
    topics: str = Query(default="negligence, causation"),
    corpus_pack: str = "sg_tort",
    jurisdiction: str = "sg",
    subject: str = "tort",
    live: bool = False,
    expose_prompt: bool = False,
    expose_provider: bool = False,
):
    request = default_pipeline_trace_request().model_copy(
        update={
            "topics": _topics_from_query(topics),
            "corpus_pack": corpus_pack,
            "jurisdiction": jurisdiction,
            "subject": subject,
            "law_domain": subject,
        }
    )
    request = GenerationRequest(**request.model_dump())
    return await pipeline_trace_service.build_trace(
        request,
        live=live,
        expose_prompt=expose_prompt,
        expose_provider=expose_provider,
    )


@router.post("/pipeline/trace")
async def pipeline_trace_post(req: PipelineTraceRequest):
    request = GenerationRequest(
        topics=req.topics,
        corpus_pack=req.corpus_pack,
        jurisdiction=req.jurisdiction,
        subject=req.subject,
        subtopics=req.subtopics,
        law_domain=req.law_domain,
        number_parties=req.number_parties,
        complexity_level=req.complexity_level,
        sample_size=req.sample_size,
        user_preferences=req.user_preferences,
    )
    return await pipeline_trace_service.build_trace(
        request,
        live=req.live,
        expose_prompt=req.expose_prompt,
        expose_provider=req.expose_provider,
    )
