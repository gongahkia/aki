"""Provider flow entrypoints for Jikai TUI."""


def providers_flow(app):
    return app._providers_flow_impl()
