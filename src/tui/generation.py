"""Generation flow entrypoints for Jikai TUI."""


def generate_flow(app):
    return app._generate_flow_impl()
