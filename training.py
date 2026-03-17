import os
import re
from pathlib import Path

from anomalib.data import MVTec
from anomalib.deploy import ExportType
from anomalib.engine import Engine
from anomalib.engine import engine as anomalib_engine
from anomalib.models import Patchcore


def _patch_anomalib_versioned_dir_for_windows() -> None:
    """Avoid Windows symlink creation for anomalib's latest directory."""
    if os.name != "nt":
        return

    def create_versioned_dir_without_symlink(root_dir: str | Path) -> Path:
        version_pattern = re.compile(r"^v(\d+)$")
        root_dir = Path(root_dir).resolve()
        root_dir.mkdir(parents=True, exist_ok=True)

        highest_version = -1
        for version_dir in root_dir.iterdir():
            if version_dir.is_dir():
                match = version_pattern.match(version_dir.name)
                if match:
                    highest_version = max(highest_version, int(match.group(1)))

        new_version_dir = root_dir / f"v{highest_version + 1}"
        new_version_dir.mkdir(exist_ok=False)
        return new_version_dir

    anomalib_engine.create_versioned_dir = create_versioned_dir_without_symlink


def _validate_mvtec_item_structure(mvtec_dataset_path: str, item_name: str) -> Path:
    dataset_root = Path(mvtec_dataset_path)
    item_root = dataset_root / item_name
    train_good_dir = item_root / "train" / "good"
    test_dir = item_root / "test"
    ground_truth_dir = item_root / "ground_truth"

    if not dataset_root.exists():
        raise ValueError(f"Dataset root does not exist: {dataset_root}")
    if not item_root.is_dir():
        raise ValueError(f"Item folder not found: {item_root}")
    if not train_good_dir.is_dir():
        raise ValueError(f"Expected training folder not found: {train_good_dir}")
    if not test_dir.is_dir():
        raise ValueError(f"Expected test folder not found: {test_dir}")

    abnormal_test_dirs = [path for path in test_dir.iterdir() if path.is_dir() and path.name != "good"]
    for defect_dir in abnormal_test_dirs:
        expected_mask_dir = ground_truth_dir / defect_dir.name
        if not expected_mask_dir.is_dir():
            raise ValueError(
                f"Missing ground truth masks for defect '{defect_dir.name}'. Expected folder: {expected_mask_dir}"
            )

        defect_images = sorted(path.stem for path in defect_dir.glob("*.png"))
        if not defect_images:
            raise ValueError(f"No PNG test images found in: {defect_dir}")

        mask_stems = {
            path.stem.removesuffix("_mask")
            for path in expected_mask_dir.glob("*.png")
        }
        missing_masks = [stem for stem in defect_images if stem not in mask_stems]
        if missing_masks:
            raise ValueError(
                "Missing ground truth mask files for defect "
                f"'{defect_dir.name}' in {expected_mask_dir}. Example missing image: {missing_masks[0]}.png"
            )

    return item_root


def train_local_item_model(mvtec_dataset_path: str, item_name: str, base_output_dir: str) -> str:
    print(f"Initializing Quality Inspection Training Pipeline for Item: '{item_name}'...")
    
    # Validate inputs
    if not mvtec_dataset_path or not item_name or not base_output_dir:
        raise ValueError(
            f"Invalid training parameters: dataset_path={mvtec_dataset_path}, "
            f"item_name={item_name}, base_output_dir={base_output_dir}"
        )
    
    print(f"Using local MVTec dataset located at: {os.path.abspath(mvtec_dataset_path)}")
    _patch_anomalib_versioned_dir_for_windows()
    _validate_mvtec_item_structure(mvtec_dataset_path, item_name)

    datamodule = MVTec(
        root=mvtec_dataset_path,
        category=item_name,
        train_batch_size=32,
        eval_batch_size=32,
        num_workers=4,
    )

    model = Patchcore(backbone="wide_resnet50_2", pre_trained=True)

    item_output_dir = os.path.join(base_output_dir, item_name)
    os.makedirs(item_output_dir, exist_ok=True)
    print(f"Model outputs will be saved to: {item_output_dir}")

    engine = Engine(
        default_root_dir=item_output_dir,
        max_epochs=1,
        accelerator="auto",
        devices=1,
    )

    print(f"Starting Model Training on 'Good' products only for '{item_name}'...")
    engine.fit(datamodule=datamodule, model=model)

    print("Exporting model to Torch (.pt) format for deployment...")
    engine.export(model=model, export_type=ExportType.TORCH, export_root=item_output_dir)

    print(f"Testing model against defective products for '{item_name}'...")
    engine.test(datamodule=datamodule, model=model)

    print(f"Training Complete! Check: {item_output_dir}")
    return os.path.join(item_output_dir, "weights", "torch", "model.pt")


if __name__ == "__main__":
    LOCAL_MVTEC_ROOT = r"C:/Users/shikh/Downloads/mvtec_anomaly_detection"
    LOCAL_OUTPUTS = r"C:/Users/shikh/OneDrive/Desktop/Computer Vision/CaughtIn4K/inspection_model_outputs"
    ITEM_TO_TRAIN = "bottle"

    if os.path.exists(LOCAL_MVTEC_ROOT):
        train_local_item_model(
            mvtec_dataset_path=LOCAL_MVTEC_ROOT,
            item_name=ITEM_TO_TRAIN,
            base_output_dir=LOCAL_OUTPUTS,
        )
    else:
        print(f"Error: The MVTec dataset path does not exist: {LOCAL_MVTEC_ROOT}")
