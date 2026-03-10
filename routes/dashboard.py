from flask import Blueprint, render_template
from flask_login import current_user, login_required

from models import User

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    all_users = User.query.all() if current_user.role == "System Administrator" else []
    return render_template("dashboard.html", user=current_user, all_users=all_users, results=None, summary=None)
