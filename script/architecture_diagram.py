"""Generate a white-background architecture diagram for this repository.

Usage:
    python3 script/architecture_diagram.py

Output:
    asset/reference/architecture.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server
from diagrams.onprem.database import Postgresql, Qdrant
from diagrams.onprem.monitoring import Prometheus
from diagrams.onprem.storage import Ceph
from diagrams.onprem.vcs import Github
from diagrams.programming.framework import Fastapi
from diagrams.programming.language import Python, Rust

GRAPH_ATTR = {
    "bgcolor": "#ffffff",
    "pad": "0.35",
    "nodesep": "0.55",
    "ranksep": "0.90",
    "splines": "ortho",
    "fontname": "Helvetica",
    "fontsize": "18",
    "labeljust": "l",
    "labelloc": "t",
}

NODE_ATTR = {
    "fontname": "Helvetica",
    "fontsize": "10",
    "fontcolor": "#0f172a",
}

EDGE_ATTR = {
    "color": "#64748b",
    "penwidth": "1.2",
    "fontname": "Helvetica",
    "fontsize": "10",
}

CLUSTER_ATTR = {
    "bgcolor": "#ffffff",
    "style": "rounded",
    "color": "#cbd5e1",
    "fontname": "Helvetica",
    "fontsize": "12",
    "labeljust": "l",
}


def main() -> None:
    with Diagram(
        "Jikai Runtime and Repository Architecture",
        filename="asset/reference/architecture",
        show=False,
        direction="LR",
        outformat="png",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        with Cluster("1) Operators and Entry Points", graph_attr=CLUSTER_ATTR):
            operator = User("Developer / Operator")
            makefile = Server(
                "Makefile\nrun api tui preprocess train\nwarmup test lint format"
            )
            python_api_entry = Python(
                "Python API entry\npython -m src.api\nor uvicorn src.api.main:app"
            )
            rust_api_monitor = Rust("Rust API monitor\n(tui/src/bin/api_monitor.rs)")
            rust_tui_bin = Rust("Rust TUI binary\n(tui/src/main.rs)")

        with Cluster("2) Rust TUI Application (tui/)", graph_attr=CLUSTER_ATTR):
            tui_app = Rust("app.rs + main.rs\nterminal runtime/event loop")
            tui_screens = Rust("screens/chat + screens/*\ncommands, jobs, reports")
            tui_http = Rust("api/client.rs\nREST calls via reqwest")
            tui_stream = Rust("api/streaming.rs\nSSE reader for /llm/stream")
            tui_state = Rust("state/* + ui/*\nlocal state, theme, widgets")

        with Cluster("3) FastAPI Surface (src/api)", graph_attr=CLUSTER_ATTR):
            fastapi_app = Fastapi("api/main.py\ncreate_app() + CORS")
            route_health = Fastapi("routes/health.py\n/health /version")
            route_chat = Fastapi("routes/chat.py\n/chat/interpret")
            route_workflow = Fastapi("routes/workflow.py\n/workflow/*")
            route_llm = Fastapi("routes/llm.py\n/llm/*")
            route_corpus = Fastapi("routes/corpus.py\n/corpus/*")
            route_db = Fastapi("routes/database.py\n/db/*")
            route_validation = Fastapi("routes/validation.py\n/validation/validate")
            route_jobs = Fastapi("routes/jobs.py\n/jobs/*")

        with Cluster(
            "4) Core Orchestration and Services (src/services + src/domain + src/config)",
            graph_attr=CLUSTER_ATTR,
        ):
            settings = Python("config/settings.py\n.env-driven typed settings")
            topic_domain = Python("domain/topics.py + packs.py\ntopic canonicalization")
            topic_guard = Python("topic_guard.py\nvalidate/canonicalize topics")
            chat_nlu = Python("chat_nlu.py\nintent + command interpretation")
            error_mapper = Python("error_mapper.py\nstable error payload mapping")
            workflow_facade = Python(
                "workflow_facade.py\nML+LLM generation orchestration"
            )
            hypo_generator = Python(
                "hypo_generator.py\nML foundation generation (required)"
            )
            hypothetical_service = Python(
                "hypothetical_service.py\nprompt + retrieval + generation pipeline"
            )
            prompt_templates = Python(
                "prompt_engineering/templates.py\ngeneration + analysis prompts"
            )
            llm_service = Python(
                "llm_service.py\nprovider selection, fallback, cost tracking"
            )
            provider_registry = Python(
                "llm_providers/base.py\nProviderRegistry + request/response models"
            )
            corpus_service = Python(
                "corpus_service.py\nload corpus + query + background indexing"
            )
            vector_service = Python(
                "vector_service.py\nSentenceTransformer embeddings + Chroma search"
            )
            validation_service = Python(
                "validation_service.py\ndeterministic topic/party/quality checks"
            )
            database_service = Python(
                "database_service.py\nSQLite history + reports + retention"
            )
            startup_checks = Python("startup_checks.py\nrequired corpus guardrails")

        with Cluster("5) ML and Background Pipelines", graph_attr=CLUSTER_ATTR):
            ml_pipeline = Python("ml/pipeline.py\ntrain/load classifier+regressor+clusterer")
            ml_models = Python("ml/classifier.py + regressor.py + clustering.py")
            preprocessor = Python("corpus_preprocessor.py\nraw -> normalized corpus")
            scraper = Python("scraper_service.py\nCommonLII/Judiciary scraping")
            warmup = Prometheus("warmup.py\nprovider probes + optional embedding init")
            migrations = Python("alembic/* + services/migrations.py\nDB migrations")

        with Cluster("6) Persistence and Artifacts", graph_attr=CLUSTER_ATTR):
            corpus_raw = Ceph("corpus/raw/*\ntxt/pdf/docx/image inputs")
            corpus_clean = Ceph("corpus/clean/tort/corpus.json")
            labelled_data = Ceph("corpus/labelled/*.csv")
            sqlite_db = Postgresql("SQLite file\n(data/jikai.db)")
            chroma_db = Qdrant("Chroma persistent store\n(./chroma_db)")
            trained_models = Ceph("models/*\nML artifacts + vectorizers")
            exports = Ceph("data/*\nexports, logs, generated assets")

        with Cluster("7) LLM Provider Adapters", graph_attr=CLUSTER_ATTR):
            provider_ollama = Python("ollama_provider.py")
            provider_openai = Python("openai_provider.py")
            provider_anthropic = Python("anthropic_provider.py")
            provider_google = Python("google_provider.py")
            provider_local = Python("local_provider.py")

        with Cluster("8) External Systems (config-dependent)", graph_attr=CLUSTER_ATTR):
            ollama_host = Server("Ollama daemon\nhttp://localhost:11434")
            openai_api = Server("OpenAI API")
            anthropic_api = Server("Anthropic API")
            google_api = Server("Google Gemini API")
            local_llama = Server("Local llama.cpp server")
            legal_sources = Server("CommonLII + Judiciary SG")

        with Cluster("9) Testing and CI", graph_attr=CLUSTER_ATTR):
            tests = Python("tests/test_services + test_ml + test_domain")
            perf_tests = Python("tests/perf/benchmark_latency.py")
            ci = Github(".github/workflows/ci.yml")

        # Operator and entrypoint wiring
        operator >> makefile
        operator >> python_api_entry
        makefile >> rust_api_monitor
        makefile >> rust_tui_bin
        makefile >> python_api_entry

        # Rust TUI flow
        rust_tui_bin >> tui_app
        tui_app >> tui_screens
        tui_app >> tui_state
        tui_screens >> tui_http
        tui_screens >> tui_stream

        # API server startup
        python_api_entry >> fastapi_app
        rust_api_monitor >> fastapi_app
        tui_http >> Edge(label="REST JSON") >> fastapi_app
        tui_stream >> Edge(label="SSE stream") >> route_llm

        # FastAPI route fan-out
        fastapi_app >> route_health
        fastapi_app >> route_chat
        fastapi_app >> route_workflow
        fastapi_app >> route_llm
        fastapi_app >> route_corpus
        fastapi_app >> route_db
        fastapi_app >> route_validation
        fastapi_app >> route_jobs

        # Route -> service wiring
        route_health >> database_service
        route_health >> corpus_service
        route_health >> llm_service
        route_chat >> chat_nlu
        route_workflow >> workflow_facade
        route_workflow >> error_mapper
        route_llm >> llm_service
        route_corpus >> corpus_service
        route_db >> database_service
        route_validation >> validation_service
        route_jobs >> preprocessor
        route_jobs >> scraper
        route_jobs >> ml_pipeline
        route_jobs >> vector_service
        route_jobs >> database_service

        # Core service orchestration
        workflow_facade >> topic_guard
        workflow_facade >> topic_domain
        workflow_facade >> hypo_generator
        workflow_facade >> hypothetical_service
        workflow_facade >> corpus_service
        workflow_facade >> database_service

        hypothetical_service >> prompt_templates
        hypothetical_service >> llm_service
        hypothetical_service >> corpus_service
        hypothetical_service >> vector_service
        hypothetical_service >> validation_service
        hypothetical_service >> database_service

        chat_nlu >> llm_service
        topic_guard >> topic_domain
        llm_service >> provider_registry
        corpus_service >> corpus_clean
        corpus_service >> vector_service
        vector_service >> chroma_db
        database_service >> sqlite_db
        startup_checks >> corpus_clean

        # Pipelines and artifacts
        preprocessor >> corpus_raw
        preprocessor >> corpus_clean
        scraper >> legal_sources
        scraper >> corpus_clean
        ml_pipeline >> ml_models
        ml_pipeline >> labelled_data
        ml_pipeline >> trained_models
        hypo_generator >> ml_pipeline
        warmup >> llm_service
        warmup >> corpus_clean
        migrations >> sqlite_db

        # Provider adapters and external endpoints
        provider_registry >> provider_ollama
        provider_registry >> provider_openai
        provider_registry >> provider_anthropic
        provider_registry >> provider_google
        provider_registry >> provider_local

        provider_ollama >> ollama_host
        provider_openai >> openai_api
        provider_anthropic >> anthropic_api
        provider_google >> google_api
        provider_local >> local_llama

        # Shared settings and outputs
        settings >> fastapi_app
        settings >> llm_service
        settings >> corpus_service
        settings >> validation_service
        settings >> workflow_facade
        settings >> warmup
        route_jobs >> exports

        # Quality and CI signals
        tests >> workflow_facade
        tests >> hypothetical_service
        tests >> llm_service
        tests >> database_service
        tests >> ml_pipeline
        perf_tests >> hypothetical_service
        ci >> tests
        ci >> perf_tests


if __name__ == "__main__":
    main()
