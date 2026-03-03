"""Render the repository architecture diagram with a white background and icon nodes.

Usage:
    .venv/bin/python asset/reference/architecture_diagram.py

Output:
    asset/reference/architecture.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.storage import S3
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server
from diagrams.onprem.database import Postgresql, Qdrant
from diagrams.onprem.monitoring import Prometheus
from diagrams.onprem.network import Nginx
from diagrams.onprem.storage import Ceph
from diagrams.onprem.vcs import Github
from diagrams.onprem.workflow import Airflow
from diagrams.programming.framework import Fastapi
from diagrams.programming.language import Python, Rust

GRAPH_ATTR = {
    "bgcolor": "#ffffff",
    "pad": "0.35",
    "nodesep": "0.6",
    "ranksep": "0.95",
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
            dev = User("Developer / Operator")
            makefile = Server("Makefile\nrun/api/tui/preprocess/train/warmup")
            py_cli = Python("Python CLI\nsrc/tui/__main__.py\n(jikai-api)")
            rust_monitor = Rust("Rust API Monitor\ntui/src/bin/api_monitor.rs")
            rust_tui_bin = Rust("Rust TUI Binary\njikai-tui")

        with Cluster("Rust TUI Application (tui/)", graph_attr=CLUSTER_ATTR):
            tui_loop = Rust("main.rs + app.rs\nterminal loop + screen stack")
            tui_screens = Rust(
                "screens/*\nGenerate, History, Providers,\nCorpus, Jobs, Export, Cleanup"
            )
            tui_api_client = Nginx("api/client.rs\nREST calls + job polling")
            tui_stream = Nginx("api/streaming.rs\nSSE parsing utilities")
            tui_ui_state = Rust("ui/widgets/* + state/*\nrendering + local TUI state")

        with Cluster("FastAPI Surface (src/api)", graph_attr=CLUSTER_ATTR):
            api_app = Fastapi("api/main.py\ncreate_app()")
            route_workflow = Fastapi("routes/workflow.py\n/generate /regenerate /report")
            route_llm = Fastapi("routes/llm.py\n/generate /stream /models /health")
            route_corpus = Fastapi("routes/corpus.py\n/topics /entries /query /add")
            route_db = Fastapi("routes/database.py\n/history /generation /statistics")
            route_jobs = Fastapi("routes/jobs.py\npreprocess/scrape/train/embed/export")
            route_validation = Fastapi("routes/validation.py\n/validate")
            route_health = Fastapi("routes/health.py\n/health /version")

        with Cluster(
            "Core Services and Domain (src/services, src/domain, src/config)",
            graph_attr=CLUSTER_ATTR,
        ):
            settings = Python("config/settings.py\n.env-driven typed settings")
            topic_domain = Python("domain/topics.py + packs.py\ncanonical tort topic registry")
            workflow_facade = Python(
                "workflow_facade.py\nrequest validation + regenerate lineage"
            )
            hypothetical_service = Python(
                "hypothetical_service.py\nmain generation orchestrator"
            )
            prompt_templates = Python(
                "prompt_engineering/templates.py\ngeneration + analysis prompts"
            )
            validation_service = Python(
                "validation_service.py\ndeterministic quality checks"
            )
            topic_guard = Python("topic_guard.py\ncanonicalize + enforce tort topics")
            llm_service = Python("llm_service.py\nprovider routing + fallback + cost")
            corpus_service = Python("corpus_service.py\ncorpus load/query/index")
            vector_service = Python("vector_service.py\nembeddings + semantic search")
            database_service = Python(
                "database_service.py\nSQLite history/reports/retention"
            )
            error_mapper = Python("error_mapper.py\nstable API error payloads")

        with Cluster("LLM Provider Layer (src/services/llm_providers)", graph_attr=CLUSTER_ATTR):
            provider_registry = Python("ProviderRegistry + LLMRequest/Response")
            provider_ollama = Server("ollama_provider.py")
            provider_openai = Server("openai_provider.py")
            provider_anthropic = Server("anthropic_provider.py")
            provider_google = Server("google_provider.py")
            provider_local = Server("local_provider.py")

        with Cluster("Data, Artifacts, and Runtime Stores", graph_attr=CLUSTER_ATTR):
            corpus_raw = Ceph("corpus/raw/*\nsource files (.txt/.pdf/.docx/.img)")
            corpus_clean = Ceph("corpus/clean/tort/corpus.json\ncanonical corpus")
            sqlite_db = Postgresql("data/jikai.db\ngeneration_history + reports")
            chroma_db = Qdrant("chroma_db/\nvector index store")
            models_dir = Ceph("models/\nclassifier/regressor/clusterer + vectorizer")
            logs = Ceph("logs/ + src/generated_log/")

        with Cluster("Pipelines and Background Tasks", graph_attr=CLUSTER_ATTR):
            preprocessor = Python(
                "corpus_preprocessor.py\nscan/extract/normalize/build corpus"
            )
            scraper = Python("scraper_service.py\nCommonLII/Judiciary/SICC/Gazette")
            ml_pipeline = Python("ml/pipeline.py + classifier/regressor/clustering")
            warmup = Prometheus("warmup.py\nprovider probes + embeddings init")
            migrations = Airflow("alembic/* + services/migrations.py\nDB schema evolution")

        with Cluster("External Systems (Optional/Config-Dependent)", graph_attr=CLUSTER_ATTR):
            ollama_host = Server("Ollama daemon\nhttp://localhost:11434")
            openai_api = Server("OpenAI API")
            anthropic_api = Server("Anthropic API")
            google_api = Server("Google Gemini API")
            local_llm = Server("Local llama.cpp server")
            aws_s3 = S3("AWS S3 bucket\noptional corpus storage")

        with Cluster("Tests and CI", graph_attr=CLUSTER_ATTR):
            service_tests = Python(
                "tests/test_services/*\norchestration, providers, DB, validation"
            )
            ml_tests = Python("tests/test_ml/*\ntraining + prediction")
            domain_tests = Python("tests/test_domain/*\ntopic canonicalization")
            perf_bench = Python("tests/perf/benchmark_latency.py")
            ci = Github(".github/workflows/ci.yml\nlint + mypy + pytest + bandit")

        with Cluster("Legacy/Compatibility", graph_attr=CLUSTER_ATTR):
            py_tui_stub = Python("src/tui/* (Python)\nAPI launcher + legacy artifacts")
            archive = Server("archive/jikai_v0 + v1\nolder implementations")

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
