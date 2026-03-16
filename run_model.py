import glob
import os
import time
import warnings

import cv2
import numpy as np
import torch
from anomalib.deploy import TorchInferencer

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


def _build_localized_heatmap(anomaly_map: np.ndarray, pred_mask: np.ndarray | None, image_shape: tuple[int, int]) -> np.ndarray:
    anomaly_map = anomaly_map.astype(np.float32)
    anomaly_map = cv2.resize(anomaly_map, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_CUBIC)

    if pred_mask is None:
        pred_mask = np.zeros(image_shape, dtype=np.uint8)
    else:
        pred_mask = pred_mask.astype(np.uint8)
        pred_mask = cv2.resize(pred_mask, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_NEAREST)

    if pred_mask.any():
        masked_scores = anomaly_map[pred_mask > 0]
        lower = float(masked_scores.min())
        upper = float(np.percentile(masked_scores, 99.5))
        if upper <= lower:
            upper = float(masked_scores.max())
        normalized = np.clip((anomaly_map - lower) / (upper - lower + 1e-6), 0.0, 1.0)

        # Soften the predicted region a bit so the overlay stays localized but readable.
        kernel = np.ones((7, 7), dtype=np.uint8)
        soft_mask = cv2.dilate(pred_mask, kernel, iterations=1).astype(np.float32)
        soft_mask = cv2.GaussianBlur(soft_mask, (0, 0), sigmaX=3, sigmaY=3)
        normalized *= np.clip(soft_mask, 0.0, 1.0)
    else:
        normalized = np.zeros(image_shape, dtype=np.float32)

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
        if orig_img is None:
            raise ValueError(f"Unable to read image: {img_path}")

        heatmap = _build_localized_heatmap(anomaly_map, pred_mask, orig_img.shape[:2])
        superimposed = cv2.addWeighted(orig_img, 0.72, heatmap, 0.28, 0)

        defect_category = os.path.basename(os.path.dirname(img_path))
        out_name = f"{defect_category}_{os.path.basename(img_path)}"
        cv2.imwrite(os.path.join(output_dir, out_name), superimposed)

        results_data.append(
            {
                "img_name": os.path.basename(img_path),
                "defect_category": defect_category,
                "score": round(score, 4),
                "status": "DEFECTIVE X" if pred_label else "GOOD OK",
                "heatmap_url": f"results/{out_name}",
            }
        )

    avg_latency = total_latency / len(image_paths)
    return results_data, {
        "total": len(image_paths),
        "avg_latency": round(avg_latency, 2),
        "fps": round(1000 / avg_latency, 2),
        "total_time_sec": round(total_latency / 1000, 2),
    }
