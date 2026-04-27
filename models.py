from datetime import datetime
from flask_login import UserMixin
from extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    access_revoked = db.Column(db.Boolean, nullable=False, default=False, server_default="0")


class InspectionRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    test_folder = db.Column(db.String(500), nullable=False)
    total_images = db.Column(db.Integer, nullable=False, default=0)
    defective_count = db.Column(db.Integer, nullable=False, default=0)
    good_count = db.Column(db.Integer, nullable=False, default=0)
    avg_latency = db.Column(db.Float, nullable=False, default=0.0)
    fps = db.Column(db.Float, nullable=False, default=0.0)
    total_time_sec = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    operator = db.relationship("User", backref=db.backref("inspection_runs", lazy=True))
    results = db.relationship(
        "InspectionImageResult",
        backref="inspection_run",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="InspectionImageResult.id.asc()",
    )


class InspectionImageResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspection_run_id = db.Column(db.Integer, db.ForeignKey("inspection_run.id"), nullable=False)
    img_name = db.Column(db.String(255), nullable=False)
    defect_category = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    heatmap_url = db.Column(db.String(500), nullable=False)


# 🔥 HUMAN-IN-THE-LOOP MODEL
class HumanReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    img_path = db.Column(db.String(500), nullable=False)
    img_name = db.Column(db.String(255))   # ⭐ NEW

    # Link back to the inspection run that generated this review item
    inspection_run_id = db.Column(db.Integer, db.ForeignKey("inspection_run.id"), nullable=True)
    inspection_run = db.relationship("InspectionRun", backref=db.backref("review_items", lazy=True))

    predicted_label = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float, nullable=False)

    # Item / product category (e.g. "bottle") – used to locate model weights
    item_name = db.Column(db.String(120), nullable=True)

    human_label = db.Column(db.String(50))
    is_correct = db.Column(db.Boolean)
    reviewed = db.Column(db.Boolean, default=False)

    # Operator-drawn defect mask (saved as PNG, relative to static/).
    # Only populated when predicted_label=GOOD and human says DEFECTIVE.
    mask_path = db.Column(db.String(500), nullable=True)

    # Set to True after a successful incremental retrain triggered by this review
    retrained = db.Column(db.Boolean, default=False)


class TrainingJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    dataset_path = db.Column(db.String(500), nullable=False)
    source_mode = db.Column(db.String(40), nullable=False, default="upload")
    status = db.Column(db.String(30), nullable=False, default="queued")
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    model_path = db.Column(db.String(500))
    message = db.Column(db.Text)
    logs = db.Column(db.Text, nullable=False, default="")
    metrics_json = db.Column(db.Text)

    requested_by = db.relationship("User", backref=db.backref("training_jobs", lazy=True))


class ModelVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    model_path = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activated_at = db.Column(db.DateTime)
    training_job_id = db.Column(db.Integer, db.ForeignKey("training_job.id"), nullable=True)
    metrics_json = db.Column(db.Text)

    training_job = db.relationship("TrainingJob", backref=db.backref("model_versions", lazy=True))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
