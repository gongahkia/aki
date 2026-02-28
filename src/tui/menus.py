"""Menu flow entrypoints for Jikai TUI."""


def main_menu(app):
    return app._main_menu_impl()


def more_menu(app):
    return app._more_menu_impl()


def tools_menu(app):
    return app._tools_menu_impl()
