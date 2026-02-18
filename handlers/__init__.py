from . import gallery


def register_all_handlers(app):
    gallery.register(app)
