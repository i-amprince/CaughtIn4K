import os
from pathlib import Path

# Put this BEFORE any other imports
os.environ["TRUST_REMOTE_CODE"] = "1"

from flask import Flask

from bootstrap import create_initial_users
from extensions import db, login_manager
from routes import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret-key-for-dev"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    local_appdata = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    app.config["MODEL_OUTPUT_DIR"] = os.path.join(local_appdata, "CaughtIn4K", "inspection_model_outputs")
    app.config["LEGACY_MODEL_OUTPUT_DIR"] = os.path.join(app.root_path, "inspection_model_outputs")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # 🔥 THIS HANDLES ALL BLUEPRINTS
    register_blueprints(app)

    return app


app = create_app()


if __name__ == "__main__":
    create_initial_users(app)
    app.run(debug=False)