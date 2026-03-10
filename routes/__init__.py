from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.ml import ml_bp


def register_blueprints(app) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ml_bp)
