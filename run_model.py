import glob
import os
import time
import warnings

import cv2
import numpy as np
import torch
from anomalib.deploy import TorchInferencer

from models import HumanReview
from extensions import db

warnings.filterwarnings("ignore", category=UserWarning, module="anomalib")


def _to_numpy(data):
    if data is None:
        return None
    if isinstance(data, np.ndarray):
        return data
    if hasattr(data, "detach"):
        data = data.detach()
    if hasattr(data, "cpu"):
        data = data.cpu()
    return np.asarray(data)


def _build_localized_heatmap(anomaly_map, pred_mask, image_shape):
    anomaly_map = anomaly_map.astype(np.float32)
    anomaly_map = cv2.resize(anomaly_map, (image_shape[1], image_shape[0]))

    if pred_mask is None:
        pred_mask = np.zeros(image_shape, dtype=np.uint8)
    else:
        pred_mask = cv2.resize(pred_mask.astype(np.uint8), (image_shape[1], image_shape[0]))

    normalized = np.clip(anomaly_map, 0, 1)
    return cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_JET)


def run_inferencer_batch(deployment_model_path, test_folder_root, output_dir):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inferencer = TorchInferencer(path=deployment_model_path, device=device)

    image_paths = glob.glob(os.path.join(test_folder_root, "*", "*.png"))
    if not image_paths:
        raise ValueError("No images found!")

    os.makedirs(output_dir, exist_ok=True)

    results_data, total_latency = [], 0.0

    for img_path in image_paths:
        start = time.perf_counter()
        prediction = inferencer.predict(image=img_path)
        total_latency += (time.perf_counter() - start) * 1000

        anomaly_map = _to_numpy(prediction.anomaly_map).squeeze()
        pred_mask = _to_numpy(getattr(prediction, "pred_mask", None))
        if pred_mask is not None:
            pred_mask = pred_mask.squeeze()

        score = float(prediction.pred_score)
        pred_label = bool(_to_numpy(prediction.pred_label).squeeze())

        orig_img = cv2.imread(img_path)

        heatmap = _build_localized_heatmap(anomaly_map, pred_mask, orig_img.shape[:2])
        superimposed = cv2.addWeighted(orig_img, 0.72, heatmap, 0.28, 0)

        defect_category = os.path.basename(os.path.dirname(img_path))
        out_name = f"{defect_category}_{os.path.basename(img_path)}"

        # 🔥 SAVE INSIDE STATIC
        static_path = os.path.join("static", "results")
        os.makedirs(static_path, exist_ok=True)

        save_path = os.path.join(static_path, out_name)
        cv2.imwrite(save_path, superimposed)

        predicted_label = "DEFECTIVE" if pred_label else "GOOD"

        # 🔥 STORE EVERY IMAGE FOR REVIEW
        review_entry = HumanReview(
            img_path=f"results/{out_name}",
            predicted_label=predicted_label,
            confidence=score,
        )
        db.session.add(review_entry)

        results_data.append(
            {
                "img_name": os.path.basename(img_path),
                "defect_category": defect_category,
                "score": round(score, 4),
                "status": predicted_label,
                "heatmap_url": f"results/{out_name}",
            }
        )

    db.session.commit()

    avg_latency = total_latency / len(image_paths)
    return results_data, {
        "total": len(image_paths),
        "avg_latency": round(avg_latency, 2),
        "fps": round(1000 / avg_latency, 2),
        "total_time_sec": round(total_latency / 1000, 2),
    }