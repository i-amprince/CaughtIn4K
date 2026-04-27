import json

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models import HumanReview, InspectionRun, ModelVersion, TrainingJob, User

dashboard_bp = Blueprint("dashboard", __name__)


def _build_admin_overview() -> dict:
    role_rows = (
        db.session.query(User.role, func.count(User.id))
        .filter_by(access_revoked=False)
        .group_by(User.role)
        .all()
    )
    role_counts = {role: count for role, count in role_rows}

    total_images, total_defective, total_good = db.session.query(
        func.coalesce(func.sum(InspectionRun.total_images), 0),
        func.coalesce(func.sum(InspectionRun.defective_count), 0),
        func.coalesce(func.sum(InspectionRun.good_count), 0),
    ).one()

    reviewed_count = HumanReview.query.filter_by(reviewed=True).count()
    correct_reviews = HumanReview.query.filter_by(reviewed=True, is_correct=True).count()
    incorrect_reviews = HumanReview.query.filter_by(reviewed=True, is_correct=False).count()
    review_accuracy = round((correct_reviews / reviewed_count) * 100, 1) if reviewed_count else None

    return {
        "total_users": User.query.filter_by(access_revoked=False).count(),
        "revoked_users": User.query.filter_by(access_revoked=True).count(),
        "role_counts": role_counts,
        "total_runs": InspectionRun.query.count(),
        "total_images": int(total_images or 0),
        "total_defective": int(total_defective or 0),
        "total_good": int(total_good or 0),
        "pending_reviews": HumanReview.query.filter_by(reviewed=False).count(),
        "reviewed_count": reviewed_count,
        "correct_reviews": correct_reviews,
        "incorrect_reviews": incorrect_reviews,
        "review_accuracy": review_accuracy,
        "pending_retrain": HumanReview.query.filter_by(
            reviewed=True,
            is_correct=False,
            retrained=False,
        ).count(),
        "unlinked_reviews": HumanReview.query.filter(
            HumanReview.inspection_run_id.is_(None)
        ).count(),
        "latest_runs": (
            InspectionRun.query
            .order_by(InspectionRun.created_at.desc())
            .limit(10)
            .all()
        ),
    }


def _parse_metrics(metrics_json: str | None) -> dict | None:
    if not metrics_json:
        return None
    try:
        return json.loads(metrics_json)
    except (TypeError, ValueError):
        return None


def _build_engineer_overview() -> dict:
    from routes.review import RETRAIN_THRESHOLD

    latest_jobs = (
        TrainingJob.query
        .order_by(TrainingJob.started_at.desc(), TrainingJob.id.desc())
        .limit(10)
        .all()
    )
    latest_completed_job = (
        TrainingJob.query
        .filter_by(status="completed")
        .order_by(TrainingJob.completed_at.desc(), TrainingJob.id.desc())
        .first()
    )
    model_versions = (
        ModelVersion.query
        .order_by(ModelVersion.item_name.asc(), ModelVersion.version_number.desc())
        .limit(20)
        .all()
    )

    pending_rows = (
        db.session.query(
            func.coalesce(HumanReview.item_name, "unknown"),
            func.count(HumanReview.id),
        )
        .filter(
            HumanReview.reviewed.is_(True),
            HumanReview.is_correct.is_(False),
            HumanReview.retrained.is_(False),
        )
        .group_by(func.coalesce(HumanReview.item_name, "unknown"))
        .order_by(func.count(HumanReview.id).desc())
        .all()
    )

    return {
        "latest_jobs": latest_jobs,
        "latest_job": latest_jobs[0] if latest_jobs else None,
        "latest_report": _parse_metrics(latest_completed_job.metrics_json) if latest_completed_job else None,
        "latest_report_job": latest_completed_job,
        "model_versions": model_versions,
        "active_model_count": ModelVersion.query.filter_by(active=True).count(),
        "completed_job_count": TrainingJob.query.filter_by(status="completed").count(),
        "failed_job_count": TrainingJob.query.filter_by(status="failed").count(),
        "running_job_count": TrainingJob.query.filter_by(status="running").count(),
        "retrain_threshold": RETRAIN_THRESHOLD,
        "retrain_queue": [
            {
                "item_name": item_name,
                "count": count,
                "remaining": max(RETRAIN_THRESHOLD - count, 0),
                "ready": count >= RETRAIN_THRESHOLD,
            }
            for item_name, count in pending_rows
        ],
    }


def build_dashboard_context(dataset_validation=None) -> dict:
    all_users = []
    history_runs = []
    admin_overview = None
    engineer_overview = None

    if current_user.role == "System Administrator":
        all_users = (
            User.query.filter(User.username.contains("@"))
            .order_by(User.access_revoked.asc(), User.role.asc(), User.username.asc())
            .all()
        )
        admin_overview = _build_admin_overview()

    if current_user.role == "Manufacturing Engineer":
        engineer_overview = _build_engineer_overview()

    if current_user.role == "Quality Operator":
        history_runs = (
            InspectionRun.query.filter_by(operator_id=current_user.id)
            .order_by(InspectionRun.created_at.desc())
            .limit(6)
            .all()
        )

    return {
        "user": current_user,
        "all_users": all_users,
        "admin_overview": admin_overview,
        "engineer_overview": engineer_overview,
        "dataset_validation": dataset_validation,
        "results": None,
        "summary": None,
        "history_runs": history_runs,
    }


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", **build_dashboard_context())


@dashboard_bp.route("/history/<int:run_id>")
@login_required
def history_detail(run_id: int):
    run = InspectionRun.query.get_or_404(run_id)

    if current_user.role != "Quality Operator" or run.operator_id != current_user.id:
        abort(403)

    run_img_names = [r.img_name for r in run.results]
    reviews = HumanReview.query.filter(HumanReview.img_name.in_(run_img_names)).all()

    review_map = {}
    for review in reviews:
        if review.img_name:
            review_map[review.img_name] = review

    return render_template(
        "history_detail.html",
        user=current_user,
        run=run,
        review_map=review_map,
    )
