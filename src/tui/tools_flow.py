"""Tools flow entrypoints for Jikai TUI."""


def tools_flow(app):
    return app._tools_menu_impl()
