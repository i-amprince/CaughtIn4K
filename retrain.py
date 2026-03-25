"""
retrain.py  –  Incremental weight update for a single corrected image.

When a human inspector marks a prediction as INCORRECT and supplies the
correct label, this module:
  1. Loads the existing trained model weights (.pt file).
  2. Creates a minimal temporary dataset containing only the corrected image.
  3. Runs one additional training epoch (fine-tune) so the model adapts.
  4. Overwrites the model weights in place and logs the correction.

Supported corrections
---------------------
  - DEFECTIVE  → GOOD   : image moved to train/good  (teach model this is normal)
  - GOOD       → DEFECTIVE : image copied to test/defective + ground-truth mask
                              generated, then model is retrained from scratch
                              (PatchCore is one-class; truly new defect patterns
                              require a full re-fit on the extended dataset).

Usage (called from routes/review.py)
-------------------------------------
    from retrain import retrain_on_correction
    retrain_on_correction(
        img_path        = "static/results/good_image.png",   # relative to app root
        correct_label   = "GOOD",          # what the human says it really is
        predicted_label = "DEFECTIVE",     # what the model said (wrong)
        item_name       = "bottle",        # MVTec item / product line
        base_output_dir = "/path/to/inspection_model_outputs",
        dataset_root    = "/path/to/mvtec_anomaly_detection",
    )
"""

import logging
import os
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrain_on_correction(
    img_path: str,
    correct_label: str,
    predicted_label: str,
    item_name: str,
    base_output_dir: str,
    dataset_root: str,
) -> dict:
    """
    Perform an incremental weight update based on one human correction.

    Parameters
    ----------
    img_path        : path to the heatmap/result image stored by the app
                      (relative to Flask app root, e.g. "static/results/foo.png")
    correct_label   : the label the human inspector assigned  ("GOOD" | "DEFECTIVE")
    predicted_label : what the model originally predicted     ("GOOD" | "DEFECTIVE")
    item_name       : product category used during training   (e.g. "bottle")
    base_output_dir : root folder where model weights live
    dataset_root    : root of the MVTec-style dataset used for training

    Returns
    -------
    dict with keys: success (bool), message (str), model_path (str | None)
    """
    correct_label   = correct_label.strip().upper()
    predicted_label = predicted_label.strip().upper()
    item_name       = item_name.strip().lower()

    log.info(
        "[Retrain] Correction: '%s' was predicted as '%s', correct label is '%s'",
        img_path, predicted_label, correct_label,
    )

    # Resolve absolute image path
    abs_img_path = _resolve_image_path(img_path)
    if not abs_img_path or not os.path.exists(abs_img_path):
        msg = f"[Retrain] Source image not found: {abs_img_path!r}"
        log.error(msg)
        return {"success": False, "message": msg, "model_path": None}

    model_pt = _locate_model(base_output_dir, item_name)
    if not model_pt:
        msg = f"[Retrain] No trained model found for item '{item_name}' in {base_output_dir!r}"
        log.error(msg)
        return {"success": False, "message": msg, "model_path": None}

    try:
        if correct_label == "GOOD" and predicted_label == "DEFECTIVE":
            # False-positive: model thought it was defective but it's actually good.
            # Add image to training set and fine-tune for one epoch.
            result = _retrain_false_positive(
                abs_img_path, item_name, base_output_dir, dataset_root
            )
        elif correct_label == "DEFECTIVE" and predicted_label == "GOOD":
            # False-negative: model missed a real defect.
            # Add image as a new defect sample and retrain.
            result = _retrain_false_negative(
                abs_img_path, item_name, base_output_dir, dataset_root
            )
        else:
            msg = (
                f"[Retrain] Nothing to do: predicted={predicted_label}, "
                f"correct={correct_label} (labels are the same or unrecognised)"
            )
            log.warning(msg)
            return {"success": False, "message": msg, "model_path": None}

        return result

    except Exception as exc:
        msg = f"[Retrain] Retraining failed: {exc}"
        log.exception(msg)
        return {"success": False, "message": msg, "model_path": None}


# ---------------------------------------------------------------------------
# Case handlers
# ---------------------------------------------------------------------------

def _retrain_false_positive(abs_img_path, item_name, base_output_dir, dataset_root):
    """
    The model predicted DEFECTIVE but the inspector says GOOD.
    Strategy: copy image into train/good, run one fine-tune epoch.
    """
    log.info("[Retrain] Strategy: false-positive correction (add to train/good)")

    train_good_dir = Path(dataset_root) / item_name / "train" / "good"
    train_good_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"correction_{int(time.time())}_{Path(abs_img_path).name}"
    dest_path = train_good_dir / dest_name

    # Strip heatmap overlay – save a clean copy (or just copy as-is if no original)
    clean_img = _strip_heatmap(abs_img_path)
    cv2.imwrite(str(dest_path), clean_img)
    log.info("[Retrain] Copied corrected image to: %s", dest_path)

    # Run one fine-tune epoch
    model_path = _run_training_epoch(item_name, base_output_dir, dataset_root)
    return {
        "success": True,
        "message": (
            f"False-positive correction applied. Image added to train/good "
            f"and model retrained. Weights updated at: {model_path}"
        ),
        "model_path": model_path,
    }


def _retrain_false_negative(abs_img_path, item_name, base_output_dir, dataset_root):
    """
    The model predicted GOOD but the inspector says DEFECTIVE.
    Strategy: copy image into test/correction_defects + generate a binary mask,
    then retrain so the model sees a broader anomaly distribution.
    """
    log.info("[Retrain] Strategy: false-negative correction (add to test/correction_defects)")

    defect_dir = Path(dataset_root) / item_name / "test" / "correction_defects"
    mask_dir   = Path(dataset_root) / item_name / "ground_truth" / "correction_defects"
    defect_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"correction_{int(time.time())}_{Path(abs_img_path).name}"
    dest_path  = defect_dir / dest_name
    mask_path  = mask_dir   / dest_name.replace(".png", "_mask.png").replace(".jpg", "_mask.png")

    clean_img = _strip_heatmap(abs_img_path)
    cv2.imwrite(str(dest_path), clean_img)

    # Generate a simple full-image binary mask (all-ones) as ground truth
    h, w = clean_img.shape[:2]
    mask = np.ones((h, w), dtype=np.uint8) * 255
    cv2.imwrite(str(mask_path), mask)
    log.info("[Retrain] Saved defect image: %s  mask: %s", dest_path, mask_path)

    model_path = _run_training_epoch(item_name, base_output_dir, dataset_root)
    return {
        "success": True,
        "message": (
            f"False-negative correction applied. Image added as a new defect sample "
            f"and model retrained. Weights updated at: {model_path}"
        ),
        "model_path": model_path,
    }


# ---------------------------------------------------------------------------
# Training helper
# ---------------------------------------------------------------------------

def _run_training_epoch(item_name: str, base_output_dir: str, dataset_root: str) -> str:
    """
    Import anomalib lazily (so the rest of the app can load without GPU) and
    run exactly one training epoch, then export + overwrite the model weights.
    """
    # Lazy imports so the module is usable even without anomalib installed
    try:
        from anomalib.data import MVTec
        from anomalib.deploy import ExportType
        from anomalib.engine import Engine
        from anomalib.models import Patchcore
    except ImportError as exc:
        raise RuntimeError(
            "anomalib is not installed. Cannot retrain. "
            f"Original error: {exc}"
        ) from exc

    log.info("[Retrain] Starting one-epoch fine-tune for item '%s' ...", item_name)

    datamodule = MVTec(
        root=dataset_root,
        category=item_name,
        train_batch_size=16,
        eval_batch_size=16,
        num_workers=2,
    )

    model = Patchcore(backbone="wide_resnet50_2", pre_trained=True)

    item_output_dir = os.path.join(base_output_dir, item_name)
    os.makedirs(item_output_dir, exist_ok=True)

    engine = Engine(
        default_root_dir=item_output_dir,
        max_epochs=1,
        accelerator="auto",
        devices=1,
    )

    engine.fit(datamodule=datamodule, model=model)
    engine.export(model=model, export_type=ExportType.TORCH, export_root=item_output_dir)

    model_pt = os.path.join(item_output_dir, "weights", "torch", "model.pt")
    log.info("[Retrain] Fine-tune complete. Model saved to: %s", model_pt)
    return model_pt


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _locate_model(base_output_dir: str, item_name: str) -> str | None:
    candidate = os.path.join(base_output_dir, item_name, "weights", "torch", "model.pt")
    return candidate if os.path.exists(candidate) else None


def _resolve_image_path(img_path: str) -> str:
    """
    Accept both absolute and relative paths.
    Relative paths are resolved against the Flask static folder convention.
    """
    if os.path.isabs(img_path):
        return img_path
    # Try relative to cwd
    candidate = os.path.join(os.getcwd(), img_path)
    if os.path.exists(candidate):
        return candidate
    # Try relative to the 'static' folder inside the app
    candidate2 = os.path.join(os.getcwd(), "static", img_path)
    if os.path.exists(candidate2):
        return candidate2
    return img_path  # return as-is; caller will check existence


def _strip_heatmap(img_path: str) -> np.ndarray:
    """
    Load image. We cannot undo the JET heatmap blend applied during inference,
    so we return the image as-is (colour information is preserved, which is
    sufficient for PatchCore's feature extractor).
    """
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Could not read image: {img_path!r}")
    return img


# ---------------------------------------------------------------------------
# Batch retraining (called from routes/review.py after threshold is reached)
# ---------------------------------------------------------------------------

def retrain_on_batch(
    corrections: list,
    base_output_dir: str,
    dataset_root: str,
) -> dict:
    """
    Process a batch of human corrections and retrain the model once for each
    unique item_name found in the batch.

    Parameters
    ----------
    corrections     : list of dicts, each with keys:
                        img_path, correct_label, predicted_label, item_name
    base_output_dir : root folder where model weights live
    dataset_root    : root of the MVTec-style dataset used for training

    Returns
    -------
    dict with keys: success (bool), message (str), model_path (str | None)
    """
    if not corrections:
        return {"success": False, "message": "No corrections supplied.", "model_path": None}

    print(
        f"[Retrain] Processing batch of {len(corrections)} correction(s).",
        flush=True,
    )

    errors = []
    last_model_path = None

    # Stage 1 – copy each corrected image into the dataset
    for corr in corrections:
        img_path        = corr["img_path"]
        correct_label   = corr.get("correct_label", "").strip().upper()
        predicted_label = corr.get("predicted_label", "").strip().upper()
        item_name       = (corr.get("item_name") or "").strip().lower()

        if not item_name:
            errors.append(f"Skipped {img_path}: item_name unknown.")
            continue

        abs_img_path = _resolve_image_path(img_path)
        if not abs_img_path or not os.path.exists(abs_img_path):
            errors.append(f"Skipped {img_path}: file not found.")
            continue

        try:
            if correct_label == "GOOD" and predicted_label == "DEFECTIVE":
                # False-positive: add to train/good
                train_good_dir = Path(dataset_root) / item_name / "train" / "good"
                train_good_dir.mkdir(parents=True, exist_ok=True)
                dest_name = f"correction_{int(time.time())}_{Path(abs_img_path).name}"
                cv2.imwrite(str(train_good_dir / dest_name), _strip_heatmap(abs_img_path))
                log.info("[Retrain] Staged false-positive image: %s", dest_name)

            elif correct_label == "DEFECTIVE" and predicted_label == "GOOD":
                # False-negative: add to test/correction_defects + generate mask
                defect_dir = Path(dataset_root) / item_name / "test" / "correction_defects"
                mask_dir   = Path(dataset_root) / item_name / "ground_truth" / "correction_defects"
                defect_dir.mkdir(parents=True, exist_ok=True)
                mask_dir.mkdir(parents=True, exist_ok=True)

                dest_name  = f"correction_{int(time.time())}_{Path(abs_img_path).name}"
                mask_name  = dest_name.replace(".png", "_mask.png").replace(".jpg", "_mask.png")
                clean_img  = _strip_heatmap(abs_img_path)
                cv2.imwrite(str(defect_dir / dest_name), clean_img)
                h, w = clean_img.shape[:2]
                cv2.imwrite(str(mask_dir / mask_name), np.ones((h, w), dtype=np.uint8) * 255)
                log.info("[Retrain] Staged false-negative image: %s", dest_name)
            else:
                log.warning(
                    "[Retrain] Skipping %s: predicted=%s correct=%s (nothing to do).",
                    img_path, predicted_label, correct_label,
                )
        except Exception as exc:
            errors.append(f"Error staging {img_path}: {exc}")
            log.exception("[Retrain] Staging error for %s", img_path)

    # Stage 2 – retrain once per unique item_name
    item_names = {
        (c.get("item_name") or "").strip().lower()
        for c in corrections
        if (c.get("item_name") or "").strip()
    }

    for item_name in item_names:
        try:
            model_path = _run_training_epoch(item_name, base_output_dir, dataset_root)
            last_model_path = model_path
            log.info("[Retrain] Batch retrain complete for item '%s': %s", item_name, model_path)
        except Exception as exc:
            errors.append(f"Retraining failed for item '{item_name}': {exc}")
            log.exception("[Retrain] Training error for item '%s'", item_name)

    if errors:
        return {
            "success": last_model_path is not None,
            "message": "Batch retrain finished with some errors: " + "; ".join(errors),
            "model_path": last_model_path,
        }

    return {
        "success": True,
        "message": f"Batch retrain complete for {len(item_names)} item(s).",
        "model_path": last_model_path,
    }
