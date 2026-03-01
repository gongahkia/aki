"""Textual screen modules for Jikai TUI."""

from .diagnostics import DiagnosticsScreen
from .demo_flow import DemoFlowScreen
from .generate import GenerateFormScreen
from .history import HistoryScreen
from .providers import ProvidersScreen
from .settings import SettingsScreen
from .setup_wizard import SetupWizardScreen

__all__ = [
    "DemoFlowScreen",
    "DiagnosticsScreen",
    "GenerateFormScreen",
    "HistoryScreen",
    "ProvidersScreen",
    "SettingsScreen",
    "SetupWizardScreen",
]
