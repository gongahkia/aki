"""Tests for Rich TUI (basic import and structure tests)."""

from src.domain import TORT_TOPICS
from src.tui import JikaiTUI
from src.tui import generation as generation_module
from src.tui import providers as providers_module


class TestTUIScreens:
    """Basic import and instantiation tests for Rich TUI."""

    def test_import_app(self):
        assert JikaiTUI is not None

    def test_instantiate_app(self):
        tui = JikaiTUI()
        assert hasattr(tui, "run")
        assert hasattr(tui, "main_menu")

    def test_topics_list(self):
        assert len(TORT_TOPICS) >= 18

    def test_providers_list(self):
        assert callable(providers_module.providers_flow)

    def test_all_flows_exist(self):
        tui = JikaiTUI()
        for method in [
            "generate_flow",
            "train_flow",
            "corpus_flow",
            "settings_flow",
            "providers_flow",
        ]:
            assert hasattr(tui, method)

    def test_corpus_parsers_exist(self):
        tui = JikaiTUI()
        for method in ["_parse_json", "_parse_csv", "_parse_txt"]:
            assert callable(getattr(tui, method))

    def test_run_async_helper(self):
        class _App:
            def _generate_flow_impl(self):
                return 42

        assert generation_module.generate_flow(_App()) == 42

    def test_package_exports(self):
        from src.tui import JikaiTUI

        assert JikaiTUI is not None
