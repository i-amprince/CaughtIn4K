import base64
import os
import threading

from flask import Blueprint, current_app, flash, render_template, request, redirect, url_for
from flask_login import login_required

from models import HumanReview
from extensions import db

review_bp = Blueprint("review", __name__)

# Global flag so the UI can poll whether retraining is in progress
_retrain_lock = threading.Lock()
_retrain_in_progress = False

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

    # Group pending items by inspection run so the UI can show one section per run.
    # Items that pre-date the inspection_run_id column (legacy) are grouped under None.
    from collections import OrderedDict
    from models import InspectionRun

    runs_map = OrderedDict()   # {InspectionRun | None: [HumanReview, ...]}
    for item in items:
        run = item.inspection_run  # relationship; None for legacy rows
        if run not in runs_map:
            runs_map[run] = []
        runs_map[run].append(item)

    # Similarly group reviewed history
    reviewed_runs_map = OrderedDict()
    for item in reviewed_items:
        run = item.inspection_run
        if run not in reviewed_runs_map:
            reviewed_runs_map[run] = []
        reviewed_runs_map[run].append(item)

    return render_template(
        "review.html",
        items=items,
        runs_map=runs_map,
        reviewed_items=reviewed_items,
        reviewed_runs_map=reviewed_runs_map,
        false_classifications_pending=false_classifications_pending,
        retrain_threshold=RETRAIN_THRESHOLD,
        retrain_in_progress=_retrain_in_progress,
    )


@review_bp.route("/retrain_status")
@login_required
def retrain_status():
    """Lightweight JSON endpoint polled by the frontend to track retraining state."""
    from flask import jsonify
    return jsonify({"in_progress": _retrain_in_progress})


@review_bp.route("/submit_review/<int:review_id>", methods=["POST"])
@login_required
def submit_review(review_id):
    item = HumanReview.query.get_or_404(review_id)

    is_correct    = request.form.get("is_correct")
    correct_label = request.form.get("correct_label", "").strip().upper()

    if is_correct == "yes":
        item.is_correct  = True
        item.human_label = item.predicted_label
        item.reviewed    = True
        db.session.commit()
        flash(f"Review #{review_id} marked as correct.", "success")

    elif is_correct == "no":
        if not correct_label:
            flash("Please provide the correct label before submitting.", "error")
            return redirect(url_for("review.review_page"))

        item.is_correct  = False
        item.human_label = correct_label
        # Not committed yet — we may need to collect a mask first

        # False-negative case: model said GOOD but inspector says DEFECTIVE.
        # Redirect to the mask-drawing page before finalising the review so
        # the operator can mark exactly where the defect is.
        if correct_label == "DEFECTIVE" and item.predicted_label.upper() == "GOOD":
            db.session.commit()   # save human_label + is_correct so draw_mask can read them
            return redirect(url_for("review.draw_mask", review_id=review_id))

        # False-positive (or other label change): no mask needed, commit and retrain check
        item.reviewed = True
        db.session.commit()
        _check_and_trigger_batch_retrain()

    else:
        flash("Invalid submission.", "error")

    return redirect(url_for("review.review_page"))


@review_bp.route("/draw_mask/<int:review_id>", methods=["GET"])
@login_required
def draw_mask(review_id):
    """Show the mask-drawing canvas for a false-negative correction."""
    item = HumanReview.query.get_or_404(review_id)
    return render_template("draw_mask.html", item=item)


@review_bp.route("/submit_mask/<int:review_id>", methods=["POST"])
@login_required
def submit_mask(review_id):
    """
    Receive the operator-drawn mask as a base64 PNG, save it to disk,
    store the path on the HumanReview row, then mark it reviewed and
    trigger the batch retrain check.
    """
    item = HumanReview.query.get_or_404(review_id)

    mask_data = request.form.get("mask_data", "")
    if not mask_data:
        flash("No mask received. Please draw the defect area before submitting.", "error")
        return redirect(url_for("review.draw_mask", review_id=review_id))

    # Decode base64 PNG sent from the canvas
    try:
        header, encoded = mask_data.split(",", 1)
        mask_bytes = base64.b64decode(encoded)
    except Exception:
        flash("Invalid mask data. Please try again.", "error")
        return redirect(url_for("review.draw_mask", review_id=review_id))

    # Save mask PNG into static/masks/
    masks_dir = os.path.join(current_app.root_path, "static", "masks")
    os.makedirs(masks_dir, exist_ok=True)

    mask_filename = f"mask_{review_id}.png"
    mask_abs_path = os.path.join(masks_dir, mask_filename)
    with open(mask_abs_path, "wb") as f:
        f.write(mask_bytes)

    item.mask_path = f"masks/{mask_filename}"
    item.reviewed  = True
    db.session.commit()

    flash("Mask saved. Correction queued for retraining.", "success")
    _check_and_trigger_batch_retrain()
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
            "warning",  # 'info' has no CSS rule; 'warning' renders correctly
        )
        return

    # We have hit (or exceeded) the threshold — mark them and fire the thread
    for item in pending_items:
        item.retrained = True
    db.session.commit()

    flash(
        f"🎯 Threshold of {RETRAIN_THRESHOLD} false classifications reached — "
        "retraining has started in the background. You can keep reviewing!",
        "retrain",
    )

    _launch_retrain_thread(pending_items)


def _launch_retrain_thread(items):
    """
    Spawn a daemon thread so retraining never blocks the HTTP response.
    We snapshot everything we need from the app context here, before
    the thread starts, so there are no SQLAlchemy/session issues.
    Sets the module-level _retrain_in_progress flag so the UI can poll
    the /retrain_status endpoint to show a live banner.
    """
    global _retrain_in_progress

    app = current_app._get_current_object()

    # Snapshot the data we need — don't pass SQLAlchemy model objects across threads
    corrections = [
        {
            "img_path":        item.img_path,
            "correct_label":   item.human_label,
            "predicted_label": item.predicted_label,
            "item_name":       getattr(item, "item_name", None) or _infer_item_name(item.img_path),
            # Absolute path to the operator-drawn mask PNG (None for false-positives)
            "mask_path": (
                os.path.join(current_app.root_path, "static", item.mask_path)
                if item.mask_path else None
            ),
        }
        for item in items
    ]

    base_output_dir = app.config.get("MODEL_OUTPUT_DIR", "")
    dataset_root    = app.config.get("DATASET_ROOT", "")

    def _run():
        global _retrain_in_progress
        with _retrain_lock:
            _retrain_in_progress = True

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

            finally:
                with _retrain_lock:
                    _retrain_in_progress = False
                print("[Retrain] Background thread finished. UI flag cleared.", flush=True)

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
