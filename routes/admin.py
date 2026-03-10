from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import User

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/create_user", methods=["POST"])
@login_required
def create_user():
    if current_user.role != "System Administrator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    new_user = User(
        username=request.form.get("username"),
        password=request.form.get("password"),
        role=request.form.get("role"),
    )
    db.session.add(new_user)
    db.session.commit()
    flash("User created successfully!", "success")
    return redirect(url_for("dashboard.dashboard"))
