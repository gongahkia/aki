"""Browser demo routes."""

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
from ..security import is_hosted_api

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


DEMO_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>Jikai Demo</title>
<style>
:root{--bg:#f7f8f5;--ink:#18211c;--muted:#5f6a62;--line:#cbd6cf;--panel:#fff;--green:#0c754c;--red:#a7342f;--blue:#265f91}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#fff;border-bottom:1px solid var(--line)}.wrap{width:min(1120px,calc(100vw - 32px));margin:0 auto}.top{min-height:70px;display:flex;align-items:center;justify-content:space-between;gap:16px}h1{margin:0;font-size:24px;letter-spacing:0}.sub{margin-top:4px;color:var(--muted);font-size:13px}.links{display:flex;gap:10px;flex-wrap:wrap}a{color:var(--blue);font-weight:700;text-decoration:none}main{display:grid;grid-template-columns:360px minmax(0,1fr);gap:14px;padding:18px 0 28px}form,.notice,.output{background:var(--panel);border:1px solid var(--line);border-radius:8px}form{display:grid;gap:10px;padding:14px;position:sticky;top:12px}label{display:grid;gap:5px;color:var(--muted);font-size:12px;font-weight:700;text-transform:uppercase}input,select,button{width:100%;min-height:36px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink);font:inherit;padding:0 10px}button{background:var(--green);border-color:var(--green);color:#fff;font-weight:750;cursor:pointer}button:disabled{opacity:.65;cursor:wait}.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.check{display:flex;align-items:center;gap:8px;min-height:36px;padding:0 10px;border:1px solid var(--line);border-radius:6px;text-transform:none}.check input{width:auto;min-height:0}.stack{display:grid;gap:10px}.notice{padding:12px;color:var(--muted);font-size:13px;line-height:1.45}.notice strong{color:var(--ink)}.output{min-height:640px;padding:16px}.status{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px;color:var(--muted);font-size:13px}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#edf2ed;color:var(--muted);font-weight:750}.pill.ok{background:#dff3e8;color:var(--green)}.pill.err{background:#ffe1de;color:var(--red)}h2{margin:0 0 8px;font-size:18px;letter-spacing:0}.section{padding:12px 0;border-top:1px solid var(--line)}.section:first-of-type{border-top:0}.body{white-space:pre-wrap;line-height:1.5}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;padding:12px;border:1px solid var(--line);border-radius:6px;background:#f9faf8;font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}@media(max-width:840px){.top{align-items:flex-start;flex-direction:column;padding:14px 0}main{grid-template-columns:1fr}.row{grid-template-columns:1fr}form{position:static}.output{min-height:0}}
</style>
</head>
<body>
<header><div class="wrap top"><div><h1>Jikai Demo</h1><div class="sub">SG Tort hypothetical generation</div></div><div class="links"><a href="/demo/pipeline">Pipeline trace</a><a href="/health">Health</a></div></div></header>
<main class="wrap">
<div class="stack">
<form id="demo-form">
<label>Jurisdiction<select id="jurisdiction"><option value="sg">Singapore</option><option value="uk">UK</option><option value="us">US</option></select></label>
<label>Topics<input id="topics" value="negligence, causation"></label>
<label>Subtopics<input id="subtopics" value="duty of care, remoteness"></label>
<div class="row"><label>Complexity<select id="complexity"><option value="intermediate">Intermediate</option><option value="beginner">Beginner</option><option value="advanced">Advanced</option></select></label><label>Parties<input id="parties" type="number" min="2" max="5" value="3"></label></div>
<label class="check"><input id="answer" type="checkbox" checked>Include model answer</label>
<button id="submit" type="submit">Generate</button>
</form>
<div class="notice"><strong>Cost/privacy:</strong> prompts and outputs are processed by the host's server-side provider. Do not enter personal, privileged, or exam-confidential material.</div>
<div class="notice">The host should keep provider keys server-side, rate-limit requests, and use request timeouts. Visitors never supply API keys.</div>
</div>
<section class="output"><div class="status"><span id="status-text">Ready</span><span id="status-pill" class="pill">idle</span></div><div id="result"><div class="section"><h2>Result</h2><div class="body">Choose SG Tort topics and generate a hypothetical.</div></div></div></section>
</main>
<script>
const $=(id)=>document.getElementById(id);
const esc=(v)=>String(v??"").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const list=(v)=>v.split(",").map((x)=>x.trim()).filter(Boolean);
function setStatus(text,mode){$("status-text").textContent=text;$("status-pill").textContent=mode;$("status-pill").className=`pill ${mode==="ok"?"ok":mode==="err"?"err":""}`}
function render(payload){$("result").innerHTML=`<div class="section"><h2>Hypothetical</h2><div class="body">${esc(payload.hypothetical)}</div></div><div class="section"><h2>Model Answer</h2><div class="body">${esc(payload.model_answer||"Not returned.")}</div></div><div class="section"><h2>Validation</h2><pre>${esc(JSON.stringify(payload.validation_results||{},null,2))}</pre></div>`}
function renderError(status,payload){const detail=payload.detail||payload;const message=detail.message||detail.code||JSON.stringify(detail);$("result").innerHTML=`<div class="section"><h2>Generation Failed</h2><div class="body">${esc(message)}</div></div><div class="section"><h2>Details</h2><pre>${esc(JSON.stringify({status,detail},null,2))}</pre></div>`}
async function generate(event){event.preventDefault();setStatus("Generating","run");$("submit").disabled=true;const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),95000);const jurisdiction=$("jurisdiction").value;const body={topics:list($("topics").value),corpus_pack:jurisdiction==="sg"?"sg_tort":`${jurisdiction}_tort`,jurisdiction,subject:"tort",law_domain:"tort",subtopics:list($("subtopics").value),number_parties:Number($("parties").value),complexity_level:$("complexity").value,sample_size:3,user_preferences:{timeout_seconds:90},include_analysis:$("answer").checked};try{const res=await fetch("/workflow/generate",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body),signal:controller.signal});const payload=await res.json();if(!res.ok){setStatus("Failed","err");renderError(res.status,payload);return}setStatus("Complete","ok");render(payload)}catch(error){setStatus("Failed","err");renderError(0,{detail:{code:error.name==="AbortError"?"client_timeout":"request_failed",message:error.name==="AbortError"?"Browser request timed out.":error.message}})}finally{clearTimeout(timer);$("submit").disabled=false}}
$("demo-form").addEventListener("submit",generate);
</script>
</body>
</html>
"""

PIPELINE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,"><title>Jikai Pipeline Trace</title><style>body{margin:0;background:#f7f8f5;color:#18211c;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{width:min(1100px,calc(100vw - 32px));margin:0 auto}header{background:#fff;border-bottom:1px solid #cbd6cf}.top{min-height:68px;display:flex;align-items:center;justify-content:space-between;gap:16px}h1{font-size:24px;margin:0;letter-spacing:0}.sub{color:#5f6a62;font-size:13px;margin-top:4px}main{padding:18px 0 28px}.controls{display:flex;gap:8px;flex-wrap:wrap}input,button{min-height:36px;border:1px solid #cbd6cf;border-radius:6px;background:#fff;color:#18211c;font:inherit;padding:0 10px}button{background:#0c754c;border-color:#0c754c;color:#fff;font-weight:750}.grid{display:grid;grid-template-columns:280px minmax(0,1fr);gap:12px;margin-top:14px}.rail,.stage,.summary{background:#fff;border:1px solid #cbd6cf;border-radius:8px}.summary{padding:12px;color:#5f6a62}.rail{display:grid;gap:6px;padding:8px;align-self:start}.rail button{background:#fff;color:#18211c;border-color:#cbd6cf;text-align:left}.rail button.active{border-color:#0c754c;box-shadow:inset 4px 0 0 #0c754c}.stage{padding:16px;min-height:520px}h2{margin:0 0 10px;font-size:18px;letter-spacing:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;padding:12px;border:1px solid #cbd6cf;border-radius:6px;background:#f9faf8;font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}@media(max-width:760px){.top{align-items:flex-start;flex-direction:column;padding:14px 0}.grid{grid-template-columns:1fr}}</style></head>
<body><header><div class="wrap top"><div><h1>Jikai Pipeline Trace</h1><div class="sub" id="mode">fixture trace</div></div><div class="controls"><input id="topics" value="negligence, causation"><button id="run">Run trace</button><a href="/demo">Demo</a></div></div></header><main class="wrap"><div class="summary" id="summary"></div><div class="grid"><nav class="rail" id="rail"></nav><section class="stage" id="stage"></section></div></main>
<script>
const $=(id)=>document.getElementById(id);const esc=(v)=>String(v??"").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));let trace=null,active=0;
function render(){const stages=trace.stages||[];$("mode").textContent=`${trace.mode} trace | ${trace.generated_at}`;$("summary").textContent=`topics: ${(trace.summary.topics||[]).join(", ")} | corpus: ${trace.summary.corpus_pack} | retrieved: ${trace.summary.retrieved_count}`;$("rail").innerHTML=stages.map((s,i)=>`<button class="${i===active?"active":""}" data-i="${i}">${esc(s.label)} - ${esc(s.status)}</button>`).join("");const s=stages[active]||{};$("stage").innerHTML=`<h2>${esc(s.label||"Trace")}</h2><pre>${esc(JSON.stringify(s.details||{},null,2))}</pre>`;document.querySelectorAll("#rail button").forEach((b)=>b.onclick=()=>{active=Number(b.dataset.i);render()})}
async function load(){const params=new URLSearchParams({topics:$("topics").value});const res=await fetch(`/demo/pipeline/trace?${params.toString()}`);if(!res.ok)throw new Error(await res.text());trace=await res.json();active=0;render()}
$("run").onclick=()=>load().catch((err)=>{$("stage").innerHTML=`<h2>Error</h2><pre>${esc(err.message)}</pre>`});load();
</script></body></html>
"""


def _topics_from_query(raw_topics: str) -> List[str]:
    return [topic.strip() for topic in raw_topics.split(",") if topic.strip()]


@router.get("", response_class=HTMLResponse)
async def generation_page() -> HTMLResponse:
    return HTMLResponse(DEMO_HTML)


@router.get("/", response_class=HTMLResponse)
async def generation_page_slash() -> HTMLResponse:
    return HTMLResponse(DEMO_HTML)


@router.get("/generate", response_class=HTMLResponse)
async def generation_page_alias() -> HTMLResponse:
    return HTMLResponse(DEMO_HTML)


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page() -> HTMLResponse:
    return HTMLResponse(PIPELINE_HTML)


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
    if is_hosted_api():
        live = False
        expose_prompt = False
        expose_provider = False
    base = default_pipeline_trace_request().model_copy(
        update={
            "topics": _topics_from_query(topics),
            "corpus_pack": corpus_pack,
            "jurisdiction": jurisdiction,
            "subject": subject,
            "law_domain": subject,
        }
    )
    request = GenerationRequest(**base.model_dump())
    return await pipeline_trace_service.build_trace(
        request,
        live=live,
        expose_prompt=expose_prompt,
        expose_provider=expose_provider,
    )


@router.post("/pipeline/trace")
async def pipeline_trace_post(req: PipelineTraceRequest):
    live = req.live
    expose_prompt = req.expose_prompt
    expose_provider = req.expose_provider
    if is_hosted_api():
        live = False
        expose_prompt = False
        expose_provider = False
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
        live=live,
        expose_prompt=expose_prompt,
        expose_provider=expose_provider,
    )
