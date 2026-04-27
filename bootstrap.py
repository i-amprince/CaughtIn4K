import os

from sqlalchemy import inspect, text

from auth_helpers import sync_bootstrap_admins
from extensions import db


def _ensure_user_access_revoked_column() -> None:
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "access_revoked" not in columns:
        db.session.execute(
            text("ALTER TABLE user ADD COLUMN access_revoked BOOLEAN NOT NULL DEFAULT 0")
        )
        db.session.commit()


def create_initial_users(app) -> None:
    with app.app_context():
        db.create_all()
        _ensure_user_access_revoked_column()
        sync_bootstrap_admins(app.config.get("GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS", []))

    os.makedirs(os.path.join(app.root_path, "static", "results"), exist_ok=True)
    os.makedirs(app.config["MODEL_OUTPUT_DIR"], exist_ok=True)
    os.makedirs(app.config["LEGACY_MODEL_OUTPUT_DIR"], exist_ok=True)
