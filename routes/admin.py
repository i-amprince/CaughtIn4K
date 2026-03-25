from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from auth_helpers import is_valid_email, normalize_email, upsert_google_user
from extensions import db

admin_bp = Blueprint("admin", __name__)

_ALLOWED_ROLES = {
    "Quality Operator",
    "Manufacturing Engineer",
    "System Administrator",
}


@admin_bp.route("/create_user", methods=["POST"])
@login_required
def create_user():
    if current_user.role != "System Administrator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    email = normalize_email(request.form.get("email"))
    role = (request.form.get("role") or "").strip()

    if not is_valid_email(email):
        flash("Enter a valid Google account email address.", "error")
        return redirect(url_for("dashboard.dashboard"))

    if role not in _ALLOWED_ROLES:
        flash("Select a valid role.", "error")
        return redirect(url_for("dashboard.dashboard"))

    _, created = upsert_google_user(email, role)
    db.session.commit()

    action_label = "authorized" if created else "updated"
    flash(f"Google account {email} {action_label} as {role}.", "success")
    return redirect(url_for("dashboard.dashboard"))
