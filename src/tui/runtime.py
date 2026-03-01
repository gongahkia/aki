"""Runtime orchestration for Rich TUI flow dispatch."""

from __future__ import annotations

from typing import Callable, Dict

from . import corpus as corpus_module
from . import generation as generation_module
from . import history as history_module
from . import providers as providers_module
from . import settings as settings_module
from . import tools_flow as tools_flow_module

FlowHandler = Callable[[object], object]


FLOW_HANDLERS: Dict[str, FlowHandler] = {
    "generate": generation_module.generate_flow,
    "history": history_module.history_flow,
    "providers": providers_module.providers_flow,
    "corpus": corpus_module.corpus_flow,
    "tools": tools_flow_module.tools_flow,
    "settings": settings_module.settings_flow,
}


def dispatch_flow(app: object, flow_name: str):
    """Dispatch a named flow via extracted Rich flow modules."""
    if flow_name not in FLOW_HANDLERS:
        raise KeyError(f"Unknown flow '{flow_name}'")
    return FLOW_HANDLERS[flow_name](app)


def run_runtime(app: object) -> None:
    """Execute Rich runtime startup then hand off to menu loop."""
    app._assert_required_corpus_ready()
    app.display_banner()
    app._start_services()
    if app._needs_first_run():
        app.first_run_wizard()
    app.main_menu()
