"""Tests for TUI screens (basic render tests)."""


class TestTUIScreens:
    """Basic import and instantiation tests for TUI screens."""

    def test_import_app(self):
        from src.tui.app import JikaiApp

        assert JikaiApp is not None

    def test_import_generate_screen(self):
        from src.tui.screens.generate import GenerateScreen

        assert GenerateScreen is not None

    def test_import_train_screen(self):
        from src.tui.screens.train import TrainScreen

        assert TrainScreen is not None

    def test_import_corpus_screen(self):
        from src.tui.screens.corpus import CorpusScreen

        assert CorpusScreen is not None

    def test_import_settings_screen(self):
        from src.tui.screens.settings import SettingsScreen

        assert SettingsScreen is not None

    def test_import_providers_screen(self):
        from src.tui.screens.providers import ProvidersScreen

        assert ProvidersScreen is not None

    def test_import_loading_widgets(self):
        from src.tui.widgets.loading import (
            LoadingSpinner,
            ProgressBarWithETA,
            StatusChecklist,
        )

        assert LoadingSpinner is not None
        assert ProgressBarWithETA is not None
        assert StatusChecklist is not None

    def test_import_topic_selector(self):
        from src.tui.widgets.topic_selector import TOPIC_CATEGORIES, TopicSelector

        assert TopicSelector is not None
        assert len(TOPIC_CATEGORIES) == 5
