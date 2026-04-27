from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models import InspectionRun, User, HumanReview

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


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    all_users = []
    history_runs = []
    admin_overview = None

    if current_user.role == "System Administrator":
        all_users = (
            User.query.filter(User.username.contains("@"))
            .order_by(User.access_revoked.asc(), User.role.asc(), User.username.asc())
            .all()
        )
        admin_overview = _build_admin_overview()

    if current_user.role == "Quality Operator":
        history_runs = (
            InspectionRun.query.filter_by(operator_id=current_user.id)
            .order_by(InspectionRun.created_at.desc())
            .limit(6)
            .all()
        )

    return render_template(
        "dashboard.html",
        user=current_user,
        all_users=all_users,
        admin_overview=admin_overview,
        results=None,
        summary=None,
        history_runs=history_runs,
    )


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
