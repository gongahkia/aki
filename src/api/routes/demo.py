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


def _topics_from_query(raw_topics: str) -> List[str]:
    return [topic.strip() for topic in raw_topics.split(",") if topic.strip()]


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page() -> HTMLResponse:
    return HTMLResponse(PIPELINE_PAGE_HTML)


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
