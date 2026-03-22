from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from models import InspectionRun, User, HumanReview

dashboard_bp = Blueprint("dashboard", __name__)


# ================= DASHBOARD =================
@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    all_users = User.query.all() if current_user.role == "System Administrator" else []
    history_runs = []

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


# ================= HISTORY DETAIL WITH HITL =================
@dashboard_bp.route("/history/<int:run_id>")
@login_required
def history_detail(run_id: int):
    run = InspectionRun.query.get_or_404(run_id)

    # 🔐 SECURITY CHECK (keep your logic intact)
    if current_user.role != "Quality Operator" or run.operator_id != current_user.id:
        abort(403)

    # 🔥 FETCH HUMAN REVIEWS
    reviews = HumanReview.query.all()

    # 🔥 MAP: image_name → review object
    review_map = {}

    for r in reviews:
        # extract filename from "results/xxx.png"
        img_name = r.img_path.split("/")[-1]
        review_map[img_name] = r

    return render_template(
        "history_detail.html",
        user=current_user,
        run=run,
        review_map=review_map,   # ⭐ NEW (important)
    )