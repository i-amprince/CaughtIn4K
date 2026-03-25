from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from models import InspectionRun, User, HumanReview

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    all_users = []
    history_runs = []

    if current_user.role == "System Administrator":
        all_users = (
            User.query.filter(User.username.contains("@"))
            .order_by(User.role.asc(), User.username.asc())
            .all()
        )

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
