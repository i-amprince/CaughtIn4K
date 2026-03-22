from flask import Blueprint, render_template, request, redirect, url_for
from models import HumanReview
from extensions import db

review_bp = Blueprint("review", __name__)


@review_bp.route("/review")
def review_page():
    items = HumanReview.query.filter_by(reviewed=False).all()
    return render_template("review.html", items=items)


@review_bp.route("/submit_review/<int:id>", methods=["POST"])
def submit_review(id):
    item = HumanReview.query.get(id)

    is_correct = request.form.get("is_correct")

    if is_correct == "yes":
        item.is_correct = True
        item.human_label = item.predicted_label
    else:
        item.is_correct = False
        item.human_label = request.form.get("correct_label")

    item.reviewed = True

    db.session.commit()

    return redirect(url_for("review.review_page"))