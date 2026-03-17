import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import InspectionImageResult, InspectionRun
from run_model import run_inferencer_batch
from training import train_local_item_model

ml_bp = Blueprint("ml", __name__)


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


@ml_bp.route("/start_training", methods=["POST"])
@login_required
def start_training():
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    dataset_path = request.form.get("dataset_path")
    item_name = request.form.get("item_name", "").strip().lower()

    if not item_name or not dataset_path or not os.path.exists(dataset_path):
        flash("Error: Invalid path or item name.", "error")
        return redirect(url_for("dashboard.dashboard"))

    base_output_dir = current_app.config.get("MODEL_OUTPUT_DIR")
    if not base_output_dir:
        flash("Error: Model output directory not configured. Contact system administrator.", "error")
        return redirect(url_for("dashboard.dashboard"))
    
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
    model_path = _resolve_model_path(item_name)

    if not model_path:
        flash(f'Model not found for item "{item_name}". Please train it first.', "error")
        return redirect(url_for("dashboard.dashboard"))

    output_dir = os.path.join(current_app.root_path, "static", "results")

    try:
        results_data, summary = run_inferencer_batch(model_path, test_folder, output_dir)

        inspection_run = InspectionRun(
            item_name=item_name,
            test_folder=test_folder,
            total_images=summary["total"],
            defective_count=sum(1 for result in results_data if "DEFECTIVE" in result["status"]),
            good_count=sum(1 for result in results_data if "GOOD" in result["status"]),
            avg_latency=summary["avg_latency"],
            fps=summary["fps"],
            total_time_sec=summary["total_time_sec"],
            operator_id=current_user.id,
        )
        db.session.add(inspection_run)
        db.session.flush()

        for result in results_data:
            db.session.add(
                InspectionImageResult(
                    inspection_run_id=inspection_run.id,
                    img_name=result["img_name"],
                    defect_category=result["defect_category"],
                    score=result["score"],
                    status=result["status"],
                    heatmap_url=result["heatmap_url"],
                )
            )

        db.session.commit()

        history_runs = (
            InspectionRun.query.filter_by(operator_id=current_user.id)
            .order_by(InspectionRun.created_at.desc())
            .limit(6)
            .all()
        )

        flash("Inspection Complete! Run saved to history.", "success")
        return render_template(
            "dashboard.html",
            user=current_user,
            all_users=[],
            results=results_data,
            summary=summary,
            history_runs=history_runs,
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Inference Error: {exc}", "error")
        return redirect(url_for("dashboard.dashboard"))
