import os, glob, time, torch, warnings, cv2
import numpy as np
from anomalib.deploy import TorchInferencer

warnings.filterwarnings("ignore", category=UserWarning, module="anomalib")

def run_inferencer_batch(deployment_model_path, test_folder_root, output_dir):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inferencer = TorchInferencer(path=deployment_model_path, device=device)
    image_paths = glob.glob(os.path.join(test_folder_root, "*", "*.png"))
    
    if not image_paths: raise ValueError("No images found!")
    os.makedirs(output_dir, exist_ok=True)
    
    results_data, total_latency = [], 0.0
    for img_path in image_paths:
        start = time.perf_counter()
        prediction = inferencer.predict(image=img_path)
        total_latency += (time.perf_counter() - start) * 1000
        
        # Heatmap processing
        anomaly_map = prediction.anomaly_map.squeeze().cpu().numpy()
        anomaly_map_norm = (anomaly_map - anomaly_map.min()) / (anomaly_map.max() - anomaly_map.min() + 1e-5)
        heatmap = cv2.applyColorMap((anomaly_map_norm * 255).astype(np.uint8), cv2.COLORMAP_JET)
        
        orig_img = cv2.imread(img_path)
        orig_img = cv2.resize(orig_img, (heatmap.shape[1], heatmap.shape[0]))
        superimposed = cv2.addWeighted(orig_img, 0.6, heatmap, 0.4, 0)
        
        out_name = f"{os.path.basename(img_path)}"
        cv2.imwrite(os.path.join(output_dir, out_name), superimposed)
        
        results_data.append({
            'img_name': os.path.basename(img_path),
            'defect_category': os.path.basename(os.path.dirname(img_path)),
            'score': round(prediction.pred_score.item() if isinstance(prediction.pred_score, torch.Tensor) else float(prediction.pred_score), 4),
            'status': "DEFECTIVE ❌" if prediction.pred_label else "GOOD ✅",
            'heatmap_url': f"results/{out_name}"
        })
    return results_data, {"total": len(image_paths), "avg_latency": round(total_latency/len(image_paths), 2), "fps": round(1000/(total_latency/len(image_paths)), 2), "total_time_sec": round(total_latency/1000, 2)}