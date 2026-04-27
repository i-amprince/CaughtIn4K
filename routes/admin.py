from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from auth_helpers import is_valid_email, normalize_email, upsert_google_user
from extensions import db
from models import User

admin_bp = Blueprint("admin", __name__)

_ALLOWED_ROLES = {
    "Quality Operator",
    "Manufacturing Engineer",
    "System Administrator",
}


def _active_admin_count() -> int:
    return User.query.filter_by(
        role="System Administrator",
        access_revoked=False,
    ).count()


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


@admin_bp.route("/update_user_role/<int:user_id>", methods=["POST"])
@login_required
def update_user_role(user_id: int):
    if current_user.role != "System Administrator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    role = (request.form.get("role") or "").strip()
    if role not in _ALLOWED_ROLES:
        flash("Select a valid role.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User account not found.", "error")
        return redirect(url_for("dashboard.dashboard"))

    admin_count = _active_admin_count()
    would_remove_last_admin = (
        user.role == "System Administrator"
        and not user.access_revoked
        and role != "System Administrator"
        and admin_count <= 1
    )
    if would_remove_last_admin:
        flash("At least one system administrator must remain.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user.role = role
    db.session.commit()

    flash(f"{user.username} role updated to {role}.", "success")
    return redirect(url_for("dashboard.dashboard"))


@admin_bp.route("/revoke_user/<int:user_id>", methods=["POST"])
@login_required
def revoke_user(user_id: int):
    if current_user.role != "System Administrator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User account not found.", "error")
        return redirect(url_for("dashboard.dashboard"))

    if user.id == current_user.id:
        flash("You cannot revoke your own access.", "error")
        return redirect(url_for("dashboard.dashboard"))

    if user.role == "System Administrator" and not user.access_revoked and _active_admin_count() <= 1:
        flash("At least one system administrator must remain.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user.access_revoked = True
    db.session.commit()

    flash(f"{user.username} access revoked.", "success")
    return redirect(url_for("dashboard.dashboard"))


@admin_bp.route("/restore_user/<int:user_id>", methods=["POST"])
@login_required
def restore_user(user_id: int):
    if current_user.role != "System Administrator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User account not found.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user.access_revoked = False
    db.session.commit()

    flash(f"{user.username} access restored.", "success")
    return redirect(url_for("dashboard.dashboard"))
