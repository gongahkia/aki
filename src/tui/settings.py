"""Settings flow entrypoints for Jikai TUI."""


def settings_flow(app):
    return app._settings_flow_impl()
