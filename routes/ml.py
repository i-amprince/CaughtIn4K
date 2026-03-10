import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from run_model import run_inferencer_batch
from training import train_local_item_model

ml_bp = Blueprint("ml", __name__)


@ml_bp.route("/start_training", methods=["POST"])
@login_required
def start_training():
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    dataset_path = request.form.get("dataset_path")
    item_name = request.form.get("item_name", "").strip().lower()

    if not item_name or not os.path.exists(dataset_path):
        flash("Error: Invalid path or item name.", "error")
        return redirect(url_for("dashboard.dashboard"))

    base_output_dir = os.path.join(current_app.root_path, "inspection_model_outputs")
    try:
        flash(f"Training started for '{item_name}'. Please wait...", "success")
        final_path = train_local_item_model(dataset_path, item_name, base_output_dir)
        flash(f"Training completed! Model ready at: {final_path}", "success")
    except Exception as exc:
        flash(f"Training Error: {exc}", "error")
    return redirect(url_for("dashboard.dashboard"))


@ml_bp.route("/run_inspection", methods=["POST"])
@login_required
def run_inspection():
    if current_user.role != "Quality Operator":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    item_name = request.form.get("item_name", "").strip().lower()
    test_folder = request.form.get("test_folder")
    model_path = os.path.join(
        current_app.root_path, "inspection_model_outputs", item_name, "weights", "torch", "model.pt"
    )

    if not os.path.exists(model_path):
        flash(f'Model not found for item "{item_name}". Please train it first.', "error")
        return redirect(url_for("dashboard.dashboard"))

    output_dir = os.path.join(current_app.root_path, "static", "results")

    try:
        results_data, summary = run_inferencer_batch(model_path, test_folder, output_dir)
        flash("Inspection Complete!", "success")
        return render_template("dashboard.html", user=current_user, results=results_data, summary=summary)
    except Exception as exc:
        flash(f"Inference Error: {exc}", "error")
        return redirect(url_for("dashboard.dashboard"))
