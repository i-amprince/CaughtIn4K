from flask import Blueprint, current_app, flash, render_template, request, redirect, url_for
from flask_login import login_required

from models import HumanReview
from extensions import db

review_bp = Blueprint("review", __name__)

# ---------------------------------------------------------------------------
# Retraining threshold
# ---------------------------------------------------------------------------

RETRAIN_THRESHOLD = 10  # Number of falsely classified images before retraining triggers


@review_bp.route("/review")
@login_required
def review_page():
    items = HumanReview.query.filter_by(reviewed=False).order_by(HumanReview.id.desc()).all()
    reviewed_items = HumanReview.query.filter_by(reviewed=True).order_by(HumanReview.id.desc()).limit(20).all()

    # Count how many false classifications are pending retraining
    false_classifications_pending = HumanReview.query.filter_by(
        reviewed=True, is_correct=False, retrained=False
    ).count()

    return render_template(
        "review.html",
        items=items,
        reviewed_items=reviewed_items,
        false_classifications_pending=false_classifications_pending,
        retrain_threshold=RETRAIN_THRESHOLD,
    )


@review_bp.route("/submit_review/<int:review_id>", methods=["POST"])
@login_required
def submit_review(review_id):
    item = HumanReview.query.get_or_404(review_id)

    is_correct = request.form.get("is_correct")
    correct_label = request.form.get("correct_label", "").strip().upper()

    if is_correct == "yes":
        item.is_correct = True
        item.human_label = item.predicted_label
        item.reviewed = True
        db.session.commit()
        flash(f"Review #{review_id} marked as correct.", "success")

    elif is_correct == "no":
        if not correct_label:
            flash("Please provide the correct label before submitting.", "error")
            return redirect(url_for("review.review_page"))

        item.is_correct = False
        item.human_label = correct_label
        item.reviewed = True
        db.session.commit()

        # Check if we've hit the threshold; trigger batched retraining if so
        _check_and_trigger_batch_retrain()

    else:
        flash("Invalid submission.", "error")

    return redirect(url_for("review.review_page"))


# ---------------------------------------------------------------------------
# Threshold-based batch retraining
# ---------------------------------------------------------------------------

def _check_and_trigger_batch_retrain():
    """
    Count falsely classified images that haven't been retrained yet.
    If the count has reached RETRAIN_THRESHOLD, kick off a background
    retraining job and mark those items so they aren't counted again.
    """
    pending_items = HumanReview.query.filter_by(
        reviewed=True, is_correct=False, retrained=False
    ).all()

    if len(pending_items) < RETRAIN_THRESHOLD:
        remaining = RETRAIN_THRESHOLD - len(pending_items)
        flash(
            f"Correction saved. {len(pending_items)}/{RETRAIN_THRESHOLD} false "
            f"classifications collected — retraining will start after {remaining} more.",
            "info",
        )
        return

    # We have hit (or exceeded) the threshold — mark them and fire the thread
    for item in pending_items:
        item.retrained = True
    db.session.commit()

    flash(
        f"Threshold of {RETRAIN_THRESHOLD} false classifications reached. "
        "Retraining started in the background!",
        "retrain",
    )

    _launch_retrain_thread(pending_items)


def _launch_retrain_thread(items):
    """
    Spawn a daemon thread so retraining never blocks the HTTP response.
    We snapshot everything we need from the app context here, before
    the thread starts, so there are no SQLAlchemy/session issues.
    """
    import threading

    app = current_app._get_current_object()

    # Snapshot the data we need — don't pass SQLAlchemy model objects across threads
    corrections = [
        {
            "img_path":        item.img_path,
            "correct_label":   item.human_label,
            "predicted_label": item.predicted_label,
            "item_name":       getattr(item, "item_name", None) or _infer_item_name(item.img_path),
        }
        for item in items
    ]

    base_output_dir = app.config.get("MODEL_OUTPUT_DIR", "")
    dataset_root    = app.config.get("DATASET_ROOT", "")

    def _run():
        with app.app_context():
            print(
                f"[Retrain] Retraining started because threshold reached "
                f"({len(corrections)} false classifications collected).",
                flush=True,
            )
            try:
                from retrain import retrain_on_batch

                if not dataset_root:
                    print(
                        "[Retrain] DATASET_ROOT is not configured — retraining aborted.",
                        flush=True,
                    )
                    return

                result = retrain_on_batch(
                    corrections=corrections,
                    base_output_dir=base_output_dir,
                    dataset_root=dataset_root,
                )

                if result["success"]:
                    print(
                        f"[Retrain] Retraining completed. "
                        f"Weights updated at: {result['model_path']}",
                        flush=True,
                    )
                else:
                    print(
                        f"[Retrain] Retraining completed with errors: {result['message']}",
                        flush=True,
                    )

            except Exception as exc:
                print(f"[Retrain] Retraining failed with exception: {exc}", flush=True)

    thread = threading.Thread(target=_run, daemon=True, name="retrain-worker")
    thread.start()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _infer_item_name(img_path):
    """
    Heuristic: img_path stored by run_model.py looks like
    'results/{defect_category}_{filename}.png'.
    Extract the first segment before the first underscore.
    """
    import os
    basename = os.path.basename(img_path)
    parts = basename.split("_")
    if parts:
        return parts[0].lower()
    return None
