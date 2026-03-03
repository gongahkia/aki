"""Render the repository architecture diagram with a white background.

Usage:
    .venv/bin/python asset/reference/architecture_diagram.py

Output:
    asset/reference/architecture.png
"""

from diagrams import Cluster, Diagram, Edge, Node

GRAPH_ATTR = {
    "bgcolor": "#ffffff",
    "pad": "0.35",
    "nodesep": "0.55",
    "ranksep": "0.85",
    "splines": "ortho",
    "fontname": "Helvetica",
    "fontsize": "18",
    "labeljust": "l",
    "labelloc": "t",
}

NODE_ATTR = {
    "shape": "box",
    "style": "rounded,filled",
    "fillcolor": "#ffffff",
    "color": "#94a3b8",
    "fontname": "Helvetica",
    "fontsize": "11",
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
    "fontsize": "13",
    "labeljust": "l",
}


def main() -> None:
    with Diagram(
        "Jikai Repository Layout and Runtime Architecture",
        filename="asset/reference/architecture",
        show=False,
        direction="LR",
        outformat="png",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        with Cluster("Entry Points and Operators", graph_attr=CLUSTER_ATTR):
            dev = Node("Developer / Operator")
            makefile = Node("Makefile\nrun/api/tui/preprocess/train/warmup")
            py_cli = Node("Python CLI\nsrc/tui/__main__.py\n(jikai-api)")
            rust_monitor = Node("Rust API Monitor\ntui/src/bin/api_monitor.rs")
            rust_tui_bin = Node("Rust TUI Binary\njikai-tui")

        with Cluster("Rust TUI Application (tui/)", graph_attr=CLUSTER_ATTR):
            tui_loop = Node("main.rs + app.rs\nterminal loop + screen stack")
            tui_screens = Node(
                "screens/*\nGenerate, History, Providers,\nCorpus, Jobs, Export, Cleanup"
            )
            tui_api_client = Node("api/client.rs\nREST calls + job polling")
            tui_stream = Node("api/streaming.rs\nSSE parsing utilities")
            tui_ui_state = Node("ui/widgets/* + state/*\nrendering + local TUI state")

        with Cluster("FastAPI Surface (src/api)", graph_attr=CLUSTER_ATTR):
            api_app = Node("api/main.py\ncreate_app()")
            route_workflow = Node("routes/workflow.py\n/generate /regenerate /report")
            route_llm = Node("routes/llm.py\n/generate /stream /models /health")
            route_corpus = Node("routes/corpus.py\n/topics /entries /query /add")
            route_db = Node("routes/database.py\n/history /generation /statistics")
            route_jobs = Node("routes/jobs.py\npreprocess/scrape/train/embed/export")
            route_validation = Node("routes/validation.py\n/validate")
            route_health = Node("routes/health.py\n/health /version")

        with Cluster("Core Services and Domain (src/services, src/domain, src/config)", graph_attr=CLUSTER_ATTR):
            settings = Node("config/settings.py\n.env-driven typed settings")
            topic_domain = Node("domain/topics.py + packs.py\ncanonical tort topic registry")
            workflow_facade = Node("workflow_facade.py\nrequest validation + regenerate lineage")
            hypothetical_service = Node("hypothetical_service.py\nmain generation orchestrator")
            prompt_templates = Node("prompt_engineering/templates.py\ngeneration + analysis prompts")
            validation_service = Node("validation_service.py\ndeterministic quality checks")
            topic_guard = Node("topic_guard.py\ncanonicalize + enforce tort topics")
            llm_service = Node("llm_service.py\nprovider routing + fallback + cost")
            corpus_service = Node("corpus_service.py\ncorpus load/query/index")
            vector_service = Node("vector_service.py\nembeddings + semantic search")
            database_service = Node("database_service.py\nSQLite history/reports/retention")
            error_mapper = Node("error_mapper.py\nstable API error payloads")

        with Cluster("LLM Provider Layer (src/services/llm_providers)", graph_attr=CLUSTER_ATTR):
            provider_registry = Node("ProviderRegistry + LLMRequest/Response")
            provider_ollama = Node("ollama_provider.py")
            provider_openai = Node("openai_provider.py")
            provider_anthropic = Node("anthropic_provider.py")
            provider_google = Node("google_provider.py")
            provider_local = Node("local_provider.py")

        with Cluster("Data, Artifacts, and Runtime Stores", graph_attr=CLUSTER_ATTR):
            corpus_raw = Node("corpus/raw/*\nsource files (.txt/.pdf/.docx/.img)")
            corpus_clean = Node("corpus/clean/tort/corpus.json\ncanonical corpus")
            sqlite_db = Node("data/jikai.db\ngeneration_history + reports")
            chroma_db = Node("chroma_db/\nvector index store")
            models_dir = Node("models/\nclassifier/regressor/clusterer + vectorizer")
            logs = Node("logs/ + src/generated_log/")

        with Cluster("Pipelines and Background Tasks", graph_attr=CLUSTER_ATTR):
            preprocessor = Node("corpus_preprocessor.py\nscan/extract/normalize/build corpus")
            scraper = Node("scraper_service.py\nCommonLII/Judiciary/SICC/Gazette")
            ml_pipeline = Node("ml/pipeline.py + classifier/regressor/clustering")
            warmup = Node("warmup.py\nprovider probes + optional embeddings init")
            migrations = Node("alembic/* + services/migrations.py\nDB schema evolution")

        with Cluster("External Systems (Optional/Config-Dependent)", graph_attr=CLUSTER_ATTR):
            ollama_host = Node("Ollama daemon\nhttp://localhost:11434")
            openai_api = Node("OpenAI API")
            anthropic_api = Node("Anthropic API")
            google_api = Node("Google Gemini API")
            local_llm = Node("Local llama.cpp server")
            aws_s3 = Node("AWS S3 bucket\noptional corpus storage")

        with Cluster("Tests and CI", graph_attr=CLUSTER_ATTR):
            service_tests = Node("tests/test_services/*\norchestration, providers, DB, validation")
            ml_tests = Node("tests/test_ml/*\ntraining + prediction")
            domain_tests = Node("tests/test_domain/*\ntopic canonicalization")
            perf_bench = Node("tests/perf/benchmark_latency.py")
            ci = Node(".github/workflows/ci.yml\nlint + mypy + pytest + bandit")

        with Cluster("Legacy/Compatibility", graph_attr=CLUSTER_ATTR):
            py_tui_stub = Node("src/tui/* (Python)\nAPI launcher + legacy artifacts")
            archive = Node("archive/jikai_v0 + v1\nolder implementations")

        # Entry wiring
        dev >> makefile
        dev >> py_cli
        makefile >> rust_monitor
        makefile >> rust_tui_bin
        py_cli >> api_app
        rust_monitor >> api_app
        rust_tui_bin >> tui_loop

        # Rust TUI internal flow
        tui_loop >> tui_screens
        tui_loop >> tui_ui_state
        tui_screens >> tui_api_client
        tui_screens >> tui_stream
        tui_stream >> tui_api_client

        # API surface wiring
        tui_api_client >> api_app
        api_app >> route_workflow
        api_app >> route_llm
        api_app >> route_corpus
        api_app >> route_db
        api_app >> route_jobs
        api_app >> route_validation
        api_app >> route_health

        # Route -> service wiring
        route_workflow >> workflow_facade
        route_workflow >> error_mapper
        route_llm >> llm_service
        route_corpus >> corpus_service
        route_db >> database_service
        route_jobs >> preprocessor
        route_jobs >> scraper
        route_jobs >> ml_pipeline
        route_jobs >> vector_service
        route_validation >> validation_service
        route_health >> database_service
        route_health >> corpus_service
        route_health >> llm_service

        # Core orchestration
        workflow_facade >> topic_guard
        workflow_facade >> corpus_service
        workflow_facade >> hypothetical_service
        workflow_facade >> database_service
        topic_guard >> topic_domain

        hypothetical_service >> prompt_templates
        hypothetical_service >> llm_service
        hypothetical_service >> validation_service
        hypothetical_service >> corpus_service
        hypothetical_service >> vector_service
        hypothetical_service >> database_service
        hypothetical_service >> settings

        corpus_service >> vector_service
        corpus_service >> corpus_clean
        corpus_service >> aws_s3

        vector_service >> chroma_db
        database_service >> sqlite_db
        llm_service >> provider_registry

        # Providers to external systems
        provider_registry >> provider_ollama
        provider_registry >> provider_openai
        provider_registry >> provider_anthropic
        provider_registry >> provider_google
        provider_registry >> provider_local

        provider_ollama >> ollama_host
        provider_openai >> openai_api
        provider_anthropic >> anthropic_api
        provider_google >> google_api
        provider_local >> local_llm

        # Pipelines and storage
        preprocessor >> corpus_raw
        preprocessor >> corpus_clean
        scraper >> corpus_clean
        ml_pipeline >> models_dir
        warmup >> llm_service
        warmup >> corpus_clean
        migrations >> sqlite_db

        # QA and maintenance
        service_tests >> workflow_facade
        service_tests >> hypothetical_service
        service_tests >> llm_service
        service_tests >> database_service
        ml_tests >> ml_pipeline
        domain_tests >> topic_domain
        perf_bench >> hypothetical_service
        ci >> service_tests
        ci >> ml_tests
        ci >> domain_tests

        # Legacy context
        py_tui_stub >> api_app
        archive >> py_tui_stub

        # Settings as shared dependency
        settings >> api_app
        settings >> llm_service
        settings >> corpus_service
        settings >> validation_service


if __name__ == "__main__":
    main()
