"""
routes/ml.py

All long-running ML operations (inspection inference, model training) are
executed on background daemon threads so the HTTP response is returned
immediately. The browser polls /inspection_status or /training_status every
few seconds to learn when the job is done, then redirects automatically.
"""

import os
import threading

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import InspectionImageResult, InspectionRun

ml_bp = Blueprint("ml", __name__)

# ---------------------------------------------------------------------------
# Shared job state (module-level, guarded by a lock per job type)
# ---------------------------------------------------------------------------

_inspection_lock = threading.Lock()
_inspection_state = {
    "running":  False,
    "done":     False,
    "success":  False,
    "message":  "",
}

_training_lock = threading.Lock()
_training_state = {
    "running": False,
    "done":    False,
    "success": False,
    "message": "",
}


def _update_inspection(updates: dict):
    with _inspection_lock:
        _inspection_state.update(updates)


def _update_training(updates: dict):
    with _training_lock:
        _training_state.update(updates)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_model_path(item_name: str) -> str | None:
    candidate_roots = [
        current_app.config["MODEL_OUTPUT_DIR"],
        current_app.config.get("LEGACY_MODEL_OUTPUT_DIR"),
    ]
    for root_dir in candidate_roots:
        if not root_dir:
            continue
        model_path = os.path.join(root_dir, item_name, "weights", "torch", "model.pt")
        if os.path.exists(model_path):
            return model_path
    return None


# ---------------------------------------------------------------------------
# Training  (Manufacturing Engineer)
# ---------------------------------------------------------------------------

@ml_bp.route("/start_training", methods=["POST"])
@login_required
def start_training():
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    dataset_path = request.form.get("dataset_path")
    item_name    = request.form.get("item_name", "").strip().lower()

    if not item_name or not dataset_path or not os.path.exists(dataset_path):
        flash("Error: Invalid path or item name.", "error")
        return redirect(url_for("dashboard.dashboard"))

    base_output_dir = current_app.config.get("MODEL_OUTPUT_DIR")
    if not base_output_dir:
        flash("Error: Model output directory not configured. Contact system administrator.", "error")
        return redirect(url_for("dashboard.dashboard"))

    with _training_lock:
        if _training_state["running"]:
            flash("A training job is already running. Please wait for it to finish.", "warning")
            return redirect(url_for("dashboard.dashboard"))
        _training_state.update({"running": True, "done": False, "success": False, "message": ""})

    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                from training import train_local_item_model
                final_path = train_local_item_model(dataset_path, item_name, base_output_dir)
                _update_training({
                    "running": False, "done": True, "success": True,
                    "message": f"Training completed! Model ready at: {final_path}",
                })
                print(f"[Training] Done. Model at: {final_path}", flush=True)
            except Exception as exc:
                _update_training({
                    "running": False, "done": True, "success": False,
                    "message": f"Training Error: {exc}",
                })
                print(f"[Training] Failed: {exc}", flush=True)

    threading.Thread(target=_run, daemon=True, name="training-worker").start()
    flash(f"Training started for '{item_name}' in the background. This page will update when done.", "info")
    return redirect(url_for("dashboard.dashboard"))


@ml_bp.route("/training_status")
@login_required
def training_status():
    """Polled by the dashboard JS every 4 s to check training progress."""
    with _training_lock:
        snapshot = dict(_training_state)
        if _training_state["done"]:
            _training_state["done"] = False
    return jsonify(snapshot)


# ---------------------------------------------------------------------------
# Inference / Inspection  (Quality Operator)
# ---------------------------------------------------------------------------

@ml_bp.route("/run_inspection", methods=["POST"])
@login_required
def run_inspection():
    if current_user.role != "Quality Operator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    item_name   = request.form.get("item_name", "").strip().lower()
    test_folder = request.form.get("test_folder")
    model_path  = _resolve_model_path(item_name)

    if not model_path:
        flash(f'Model not found for item "{item_name}". Please train it first.', "error")
        return redirect(url_for("dashboard.dashboard"))

    with _inspection_lock:
        if _inspection_state["running"]:
            flash("An inspection is already running. Please wait for it to finish.", "warning")
            return redirect(url_for("dashboard.dashboard"))
        _inspection_state.update({
            "running": True, "done": False, "success": False,
            "message": "",
        })

    app        = current_app._get_current_object()
    output_dir = os.path.join(app.root_path, "static", "results")
    user_id    = current_user.id

    def _run():
        with app.app_context():
            try:
                from run_model import run_inferencer_batch
                results_data, summary = run_inferencer_batch(model_path, test_folder, output_dir)

                inspection_run = InspectionRun(
                    item_name=item_name,
                    test_folder=test_folder,
                    total_images=summary["total"],
                    defective_count=sum(1 for r in results_data if "DEFECTIVE" in r["status"]),
                    good_count=sum(1 for r in results_data if "GOOD" in r["status"]),
                    avg_latency=summary["avg_latency"],
                    fps=summary["fps"],
                    total_time_sec=summary["total_time_sec"],
                    operator_id=user_id,
                )
                db.session.add(inspection_run)
                db.session.flush()

                for result in results_data:
                    db.session.add(InspectionImageResult(
                        inspection_run_id=inspection_run.id,
                        img_name=result["img_name"],
                        defect_category=result["defect_category"],
                        score=result["score"],
                        status=result["status"],
                        heatmap_url=result["heatmap_url"],
                    ))

                db.session.commit()
                print(f"[Inspection] Done. {summary['total']} images, run id={inspection_run.id}", flush=True)
                _update_inspection({
                    "running": False, "done": True, "success": True,
                    "message": "Inspection complete! Results saved.",
                })

            except Exception as exc:
                db.session.rollback()
                print(f"[Inspection] Failed: {exc}", flush=True)
                _update_inspection({
                    "running": False, "done": True, "success": False,
                    "message": f"Inference Error: {exc}",
                })

    threading.Thread(target=_run, daemon=True, name="inspection-worker").start()
    flash("Inspection started in the background. Results will appear when complete.", "info")
    return redirect(url_for("dashboard.dashboard"))


@ml_bp.route("/inspection_status")
@login_required
def inspection_status():
    """Polled by the dashboard JS every 4 s to check inspection progress."""
    with _inspection_lock:
        snapshot = dict(_inspection_state)
        if _inspection_state["done"]:
            _inspection_state["done"] = False
    return jsonify(snapshot)
