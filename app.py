import os

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

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    register_blueprints(app)
    return app


app = create_app()


if __name__ == "__main__":
    create_initial_users(app)
    app.run(debug=False)
