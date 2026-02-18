"""Jikai TUI Utilities."""

import asyncio


def run_async(coro):
    """Run async coroutine from synchronous context."""
    return asyncio.run(coro)
