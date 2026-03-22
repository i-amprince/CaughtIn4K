from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.ml import ml_bp
from .review import review_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(review_bp)
