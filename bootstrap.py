import os

from extensions import db
from models import User


def create_initial_users(app) -> None:
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(username="admin", password="123", role="System Administrator"))
            db.session.add(User(username="inspector", password="123", role="Quality Operator"))
            db.session.add(User(username="engineer", password="123", role="Manufacturing Engineer"))
            db.session.commit()

    os.makedirs(os.path.join(app.root_path, "static", "results"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "inspection_model_outputs"), exist_ok=True)
