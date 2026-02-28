"""History flow entrypoints for Jikai TUI."""


def history_flow(app):
    return app._history_flow_impl()
