"""
routes/ml.py

All long-running ML operations (inspection inference, model training) are
executed on background daemon threads so the HTTP response is returned
immediately. The browser polls /inspection_status or /training_status every
few seconds to learn when the job is done, then redirects automatically.
"""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from extensions import db
from models import HumanReview, InspectionImageResult, InspectionRun, ModelVersion, TrainingJob

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
    "job_id":  None,
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
    active_version = (
        ModelVersion.query
        .filter_by(item_name=item_name, active=True)
        .order_by(ModelVersion.version_number.desc())
        .first()
    )
    if active_version and os.path.exists(active_version.model_path):
        return active_version.model_path

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


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _append_training_log(job_id: int, message: str) -> None:
    job = db.session.get(TrainingJob, job_id)
    if not job:
        return
    timestamp = datetime.utcnow().strftime("%H:%M:%S")
    job.logs = ((job.logs or "") + f"[{timestamp}] {message}\n")[-12000:]
    db.session.commit()


def _upload_destination(kind: str) -> Path:
    root = Path(current_app.config["USER_UPLOAD_ROOT"]) / kind
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def _safe_relative_parts(filename: str) -> list[str]:
    normalized = filename.replace("\\", "/")
    parts = []
    for raw_part in normalized.split("/"):
        if raw_part in ("", ".", ".."):
            continue
        clean_part = secure_filename(raw_part)
        if clean_part:
            parts.append(clean_part)
    return parts


def _save_uploaded_tree(field_name: str, kind: str) -> Path | None:
    files = [file for file in request.files.getlist(field_name) if file and file.filename]
    if not files:
        return None

    destination = _upload_destination(kind)
    saved_count = 0
    destination_resolved = destination.resolve()

    for file in files:
        parts = _safe_relative_parts(file.filename)
        if not parts:
            continue

        target = destination.joinpath(*parts).resolve()
        if destination_resolved not in target.parents and target != destination_resolved:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        file.save(target)
        saved_count += 1

    if saved_count == 0:
        raise ValueError("No files were uploaded from the selected folder.")
    return destination


def _find_dataset_root_for_item(upload_root: Path, item_name: str) -> Path:
    candidates = [upload_root]
    candidates.extend(path for path in upload_root.iterdir() if path.is_dir())

    for candidate in candidates:
        if (candidate / item_name / "train" / "good").is_dir():
            return candidate
    return upload_root


def _find_test_folder_root(upload_root: Path) -> Path:
    candidates = [upload_root]
    candidates.extend(path for path in upload_root.rglob("*") if path.is_dir())

    valid_candidates = [
        candidate
        for candidate in candidates
        if list(candidate.glob("*/*.png"))
    ]
    if not valid_candidates:
        return upload_root

    for candidate in valid_candidates:
        if candidate.name.lower() == "test":
            return candidate
    return min(valid_candidates, key=lambda path: len(path.parts))


def _resolve_dataset_input(item_name: str) -> tuple[str, str]:
    uploaded_root = _save_uploaded_tree("dataset_folder", "training")
    if uploaded_root:
        return str(_find_dataset_root_for_item(uploaded_root, item_name)), "upload"

    dataset_path = request.form.get("dataset_path", "").strip()
    if dataset_path:
        return dataset_path, "path"

    raise ValueError("Choose a dataset folder before starting training.")


def _resolve_test_folder_input() -> tuple[str, str]:
    uploaded_root = _save_uploaded_tree("test_folder_upload", "inspection")
    if uploaded_root:
        return str(_find_test_folder_root(uploaded_root)), "upload"

    test_folder = request.form.get("test_folder", "").strip()
    if test_folder:
        return test_folder, "path"

    raise ValueError("Choose a test image folder before starting inspection.")


def _next_model_version(item_name: str) -> int:
    latest = (
        db.session.query(func.max(ModelVersion.version_number))
        .filter_by(item_name=item_name)
        .scalar()
    )
    return int(latest or 0) + 1


def _deployment_model_path(item_name: str) -> Path:
    return Path(current_app.config["MODEL_OUTPUT_DIR"]) / item_name / "weights" / "torch" / "model.pt"


def _activate_model_version_record(version: ModelVersion) -> None:
    source_path = Path(version.model_path)
    if not source_path.exists():
        raise ValueError(f"Stored model file not found: {source_path}")

    deploy_path = _deployment_model_path(version.item_name)
    deploy_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != deploy_path.resolve():
        shutil.copy2(source_path, deploy_path)

    ModelVersion.query.filter_by(item_name=version.item_name).update({"active": False})
    version.active = True
    version.activated_at = datetime.utcnow()


def _register_model_version(
    item_name: str,
    model_path: str,
    training_job: TrainingJob,
    metrics_json: str | None,
) -> ModelVersion:
    source_path = Path(model_path)
    if not source_path.exists():
        raise ValueError(f"Trained model file not found: {source_path}")

    version_number = _next_model_version(item_name)
    registry_dir = Path(current_app.config["MODEL_OUTPUT_DIR"]) / "model_registry" / item_name / f"v{version_number}"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_model_path = registry_dir / "model.pt"
    shutil.copy2(source_path, registry_model_path)

    version = ModelVersion(
        item_name=item_name,
        version_number=version_number,
        model_path=str(registry_model_path),
        active=False,
        training_job_id=training_job.id,
        metrics_json=metrics_json,
    )
    db.session.add(version)
    db.session.flush()
    _activate_model_version_record(version)
    return version


# ---------------------------------------------------------------------------
# Training  (Manufacturing Engineer)
# ---------------------------------------------------------------------------

@ml_bp.route("/validate_dataset", methods=["POST"])
@login_required
def validate_dataset():
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    item_name = request.form.get("item_name", "").strip().lower()
    if not item_name:
        flash("Enter an item name before validating the dataset.", "error")
        return redirect(url_for("dashboard.dashboard"))

    try:
        dataset_path, source_mode = _resolve_dataset_input(item_name)

        from training import build_mvtec_dataset_report
        report = build_mvtec_dataset_report(dataset_path, item_name)
        report["source_mode"] = source_mode
        report["valid"] = True
        flash("Dataset structure is valid for training.", "success")

    except Exception as exc:
        report = {
            "valid": False,
            "item_name": item_name,
            "message": str(exc),
        }
        flash(f"Dataset validation failed: {exc}", "error")

    from routes.dashboard import build_dashboard_context
    return render_template("dashboard.html", **build_dashboard_context(dataset_validation=report))


@ml_bp.route("/start_training", methods=["POST"])
@login_required
def start_training():
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    item_name    = request.form.get("item_name", "").strip().lower()

    if not item_name:
        flash("Error: Item name is required.", "error")
        return redirect(url_for("dashboard.dashboard"))

    try:
        dataset_path, source_mode = _resolve_dataset_input(item_name)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.dashboard"))

    if not os.path.exists(dataset_path):
        flash("Error: Invalid dataset folder.", "error")
        return redirect(url_for("dashboard.dashboard"))

    base_output_dir = current_app.config.get("MODEL_OUTPUT_DIR")
    if not base_output_dir:
        flash("Error: Model output directory not configured. Contact system administrator.", "error")
        return redirect(url_for("dashboard.dashboard"))

    with _training_lock:
        if _training_state["running"]:
            flash("A training job is already running. Please wait for it to finish.", "warning")
            return redirect(url_for("dashboard.dashboard"))

        job = TrainingJob(
            item_name=item_name,
            dataset_path=dataset_path,
            source_mode=source_mode,
            status="queued",
            requested_by_id=current_user.id,
            message="Training queued.",
        )
        db.session.add(job)
        db.session.commit()

        _training_state.update({
            "running": True,
            "done": False,
            "success": False,
            "message": "",
            "job_id": job.id,
        })

    app = current_app._get_current_object()
    job_id = job.id

    def _run():
        with app.app_context():
            job = db.session.get(TrainingJob, job_id)
            try:
                if not job:
                    raise RuntimeError("Training job record was not found.")

                job.status = "running"
                job.started_at = datetime.utcnow()
                job.message = "Training started."
                db.session.commit()

                _append_training_log(job.id, "Training worker started.")

                from training import train_local_item_model
                report = train_local_item_model(
                    dataset_path,
                    item_name,
                    base_output_dir,
                    progress_callback=lambda message: _append_training_log(job.id, message),
                    return_report=True,
                )
                final_path = report["model_path"]
                metrics_json = json.dumps(report, default=_json_default)
                version = _register_model_version(item_name, final_path, job, metrics_json)

                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.model_path = version.model_path
                job.metrics_json = metrics_json
                job.message = f"Training completed. Model version v{version.version_number} is active."
                db.session.commit()

                _update_training({
                    "running": False,
                    "done": True,
                    "success": True,
                    "message": job.message,
                    "job_id": job.id,
                })
                print(f"[Training] Done. Model at: {version.model_path}", flush=True)
            except Exception as exc:
                db.session.rollback()
                if job:
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    job.message = f"Training Error: {exc}"
                    job.logs = ((job.logs or "") + f"[{datetime.utcnow().strftime('%H:%M:%S')}] Training failed: {exc}\n")[-12000:]
                    db.session.commit()
                _update_training({
                    "running": False,
                    "done": True,
                    "success": False,
                    "message": f"Training Error: {exc}",
                    "job_id": job.id if job else job_id,
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


@ml_bp.route("/activate_model/<int:model_id>", methods=["POST"])
@login_required
def activate_model(model_id: int):
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    version = ModelVersion.query.get_or_404(model_id)
    try:
        _activate_model_version_record(version)
        db.session.commit()
        flash(
            f"{version.item_name.title()} model v{version.version_number} is now active.",
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not activate model version: {exc}", "error")

    return redirect(url_for("dashboard.dashboard"))


@ml_bp.route("/start_feedback_retrain/<item_name>", methods=["POST"])
@login_required
def start_feedback_retrain(item_name: str):
    if current_user.role != "Manufacturing Engineer":
        flash("Permission Denied.", "error")
        return redirect(url_for("dashboard.dashboard"))

    item_name = item_name.strip().lower()
    dataset_root = current_app.config.get("DATASET_ROOT", "")
    base_output_dir = current_app.config.get("MODEL_OUTPUT_DIR", "")

    if not dataset_root:
        flash("DATASET_ROOT is not configured, so feedback retraining cannot start.", "error")
        return redirect(url_for("dashboard.dashboard"))

    pending_items = (
        HumanReview.query
        .filter(
            HumanReview.reviewed.is_(True),
            HumanReview.is_correct.is_(False),
            HumanReview.retrained.is_(False),
            HumanReview.item_name == item_name,
        )
        .all()
    )
    if not pending_items:
        flash(f"No pending corrections found for '{item_name}'.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    from routes.review import RETRAIN_THRESHOLD
    if len(pending_items) < RETRAIN_THRESHOLD:
        remaining = RETRAIN_THRESHOLD - len(pending_items)
        flash(f"{remaining} more correction(s) are needed before retraining '{item_name}'.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    with _training_lock:
        if _training_state["running"]:
            flash("A training or retraining job is already running.", "warning")
            return redirect(url_for("dashboard.dashboard"))

        job = TrainingJob(
            item_name=item_name,
            dataset_path=dataset_root,
            source_mode="feedback",
            status="queued",
            requested_by_id=current_user.id,
            message=f"Feedback retraining queued with {len(pending_items)} correction(s).",
        )
        db.session.add(job)
        for item in pending_items:
            item.retrained = True
        db.session.commit()

        _training_state.update({
            "running": True,
            "done": False,
            "success": False,
            "message": "",
            "job_id": job.id,
        })

    app = current_app._get_current_object()
    job_id = job.id
    corrections = [
        {
            "img_path":        item.img_path,
            "correct_label":   item.human_label,
            "predicted_label": item.predicted_label,
            "item_name":       item.item_name,
            "mask_path": (
                os.path.join(current_app.root_path, "static", item.mask_path)
                if item.mask_path else None
            ),
        }
        for item in pending_items
    ]

    def _run():
        with app.app_context():
            job = db.session.get(TrainingJob, job_id)
            try:
                if not job:
                    raise RuntimeError("Retraining job record was not found.")

                job.status = "running"
                job.started_at = datetime.utcnow()
                job.message = "Feedback retraining started."
                db.session.commit()
                _append_training_log(job.id, f"Feedback retraining started with {len(corrections)} correction(s).")

                from retrain import retrain_on_batch
                result = retrain_on_batch(
                    corrections=corrections,
                    base_output_dir=base_output_dir,
                    dataset_root=dataset_root,
                )
                _append_training_log(job.id, result.get("message", "Feedback retraining finished."))

                if not result.get("success"):
                    raise RuntimeError(result.get("message", "Feedback retraining failed."))

                metrics_json = json.dumps({
                    "dataset": {"dataset_path": dataset_root, "item_name": item_name},
                    "feedback_corrections": len(corrections),
                    "retrain_result": result,
                    "model_path": result.get("model_path"),
                }, default=_json_default)
                version = _register_model_version(item_name, result["model_path"], job, metrics_json)

                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.model_path = version.model_path
                job.metrics_json = metrics_json
                job.message = f"Feedback retraining completed. Model version v{version.version_number} is active."
                db.session.commit()
                _update_training({
                    "running": False,
                    "done": True,
                    "success": True,
                    "message": job.message,
                    "job_id": job.id,
                })

            except Exception as exc:
                db.session.rollback()
                if job:
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    job.message = f"Feedback retraining error: {exc}"
                    job.logs = ((job.logs or "") + f"[{datetime.utcnow().strftime('%H:%M:%S')}] Feedback retraining failed: {exc}\n")[-12000:]
                    db.session.commit()
                _update_training({
                    "running": False,
                    "done": True,
                    "success": False,
                    "message": f"Feedback retraining error: {exc}",
                    "job_id": job.id if job else job_id,
                })

    threading.Thread(target=_run, daemon=True, name="feedback-retrain-worker").start()
    flash(f"Feedback retraining started for '{item_name}'.", "info")
    return redirect(url_for("dashboard.dashboard"))


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
    model_path  = _resolve_model_path(item_name)

    if not model_path:
        flash(f'Model not found for item "{item_name}". Please train it first.', "error")
        return redirect(url_for("dashboard.dashboard"))

    try:
        test_folder, _source_mode = _resolve_test_folder_input()
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.dashboard"))

    if not os.path.exists(test_folder):
        flash("Error: Invalid test image folder.", "error")
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

                # Create the InspectionRun record first so we have its ID
                # to link HumanReview items back to this run.
                inspection_run = InspectionRun(
                    item_name=item_name,
                    test_folder=test_folder,
                    total_images=0,
                    defective_count=0,
                    good_count=0,
                    avg_latency=0.0,
                    fps=0.0,
                    total_time_sec=0.0,
                    operator_id=user_id,
                )
                db.session.add(inspection_run)
                db.session.flush()  # get inspection_run.id before running inference

                results_data, summary = run_inferencer_batch(
                    model_path, test_folder, output_dir,
                    inspection_run_id=inspection_run.id,
                    item_name=item_name,
                )

                # Update the run with real summary values
                inspection_run.total_images   = summary["total"]
                inspection_run.defective_count = sum(1 for r in results_data if "DEFECTIVE" in r["status"])
                inspection_run.good_count      = sum(1 for r in results_data if "GOOD"      in r["status"])
                inspection_run.avg_latency     = summary["avg_latency"]
                inspection_run.fps             = summary["fps"]
                inspection_run.total_time_sec  = summary["total_time_sec"]

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
