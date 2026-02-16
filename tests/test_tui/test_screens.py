"""Tests for Rich TUI (basic import and structure tests)."""


class TestTUIScreens:
    """Basic import and instantiation tests for Rich TUI."""

    def test_import_app(self):
        from src.tui.rich_app import JikaiTUI

        assert JikaiTUI is not None

    def test_instantiate_app(self):
        from src.tui.rich_app import JikaiTUI

        tui = JikaiTUI()
        assert hasattr(tui, "run")
        assert hasattr(tui, "main_menu")

    def test_topics_list(self):
        from src.tui.rich_app import TOPICS

        assert len(TOPICS) >= 18

    def test_providers_list(self):
        from src.tui.rich_app import PROVIDERS

        assert PROVIDERS == ["ollama", "openai", "anthropic", "google", "local"]

    def test_all_flows_exist(self):
        from src.tui.rich_app import JikaiTUI

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
        from src.tui.rich_app import JikaiTUI

        tui = JikaiTUI()
        for method in ["_parse_json", "_parse_csv", "_parse_txt"]:
            assert callable(getattr(tui, method))

    def test_run_async_helper(self):
        from src.tui.rich_app import _run_async

        async def _coro():
            return 42

        assert _run_async(_coro()) == 42

    def test_package_exports(self):
        from src.tui import JikaiTUI

        assert JikaiTUI is not None
