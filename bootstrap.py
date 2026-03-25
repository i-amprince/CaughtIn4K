import os

from auth_helpers import sync_bootstrap_admins
from extensions import db


def create_initial_users(app) -> None:
    with app.app_context():
        db.create_all()
        sync_bootstrap_admins(app.config.get("GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS", []))

    os.makedirs(os.path.join(app.root_path, "static", "results"), exist_ok=True)
    os.makedirs(app.config["MODEL_OUTPUT_DIR"], exist_ok=True)
    os.makedirs(app.config["LEGACY_MODEL_OUTPUT_DIR"], exist_ok=True)
