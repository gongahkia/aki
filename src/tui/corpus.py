"""Corpus flow entrypoints for Jikai TUI."""


def corpus_flow(app):
    return app._corpus_flow_impl()
