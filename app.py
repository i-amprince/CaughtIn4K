import os
from pathlib import Path

# Put this BEFORE any other imports
os.environ["TRUST_REMOTE_CODE"] = "1"

from flask import Flask

from bootstrap import create_initial_users
from extensions import db, login_manager
from routes import register_blueprints


def load_local_env(env_path: str = ".env") -> None:
    env_file = Path(env_path)
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret-key-for-dev"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET", "")
    app.config["GOOGLE_OAUTH_REDIRECT_URI"] = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
    app.config["GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS"] = [
        email.strip().lower()
        for email in os.getenv("GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]

    local_appdata = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    app.config["MODEL_OUTPUT_DIR"] = os.path.join(local_appdata, "CaughtIn4K", "inspection_model_outputs")
    app.config["LEGACY_MODEL_OUTPUT_DIR"] = os.path.join(app.root_path, "inspection_model_outputs")
    app.config["USER_UPLOAD_ROOT"] = os.path.join(local_appdata, "CaughtIn4K", "uploaded_folders")
    # Path to your MVTec-style dataset root (needed for incremental retraining).
    # Override via the DATASET_ROOT environment variable or set it directly here.
    app.config["DATASET_ROOT"] = os.getenv("DATASET_ROOT", "")

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
