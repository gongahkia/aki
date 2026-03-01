"""Dependency installer utilities for TUI flows."""

import subprocess
import sys
from typing import Callable, Protocol, Sequence

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)


class ConfirmFn(Protocol):
    def __call__(self, message: str, default: bool = False) -> bool: ...


def request_install_confirmation(
    service_key: str, dependencies: Sequence[str], confirm: ConfirmFn
) -> bool:
    dep_list = ", ".join(dependencies)
    return bool(
        confirm(
            f"Install missing packages for {service_key}? ({dep_list})",
            default=False,
        )
    )


def install_service_dependencies(
    service_key: str,
    dependencies: Sequence[str],
    console: Console,
    on_chromadb_installed: Callable[[], None] | None = None,
) -> bool:
    if not dependencies:
        return True

    console.print(f"[cyan]Installing dependencies for {service_key}...[/cyan]")
    failed: list[str] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Installing {service_key} deps", total=len(dependencies)
        )
        for package in dependencies:
            progress.update(task, description=f"[cyan]Installing {package}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--quiet"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                failed.append(package)
            progress.advance(task)

    if failed:
        console.print(f"[red]✗ Failed to install: {', '.join(failed)}[/red]")
        return False

    console.print(f"[green]✓ Dependencies for {service_key} installed.[/green]")
    if (
        on_chromadb_installed
        and "chromadb" in dependencies
        and sys.version_info >= (3, 14)
    ):
        on_chromadb_installed()
    return True
