# routes/__init__.py

from .auth import auth_bp
from .crop import crop_bp
from .admin import admin_bp
from .main import main_bp
from .camera import camera_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(crop_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(camera_bp)