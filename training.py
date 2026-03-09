import os
from anomalib.data import MVTec
from anomalib.models import Patchcore
from anomalib.engine import Engine
from anomalib.deploy import ExportType  # <--- FIXED: Changed from ExportMode to ExportType

def train_local_item_model(mvtec_dataset_path: str, item_name: str, base_output_dir: str) -> str:
    print(f"Initializing Quality Inspection Training Pipeline for Item: '{item_name}'...")
    print(f"Using local MVTec dataset located at: {os.path.abspath(mvtec_dataset_path)}")

    # Set up data module
    datamodule = MVTec(
        root=mvtec_dataset_path,
        category=item_name,
        train_batch_size=32,
        eval_batch_size=32,
        num_workers=4 
    )

    # Set up model
    model = Patchcore(
        backbone="wide_resnet50_2",
        pre_trained=True
    )

    # Create dynamic output directory
    item_output_dir = os.path.join(base_output_dir, item_name)
    os.makedirs(item_output_dir, exist_ok=True)
    print(f"Model outputs will be saved to: {item_output_dir}")

    # Initialize Engine
    engine = Engine(
        default_root_dir=item_output_dir,
        max_epochs=1,
        accelerator="auto", 
        devices=1,
    )

    print(f"Starting Model Training on 'Good' products only for '{item_name}'...")
    engine.fit(datamodule=datamodule, model=model)

    # --- EXPORT TO .PT FORMAT ---
    print(f"Exporting model to Torch (.pt) format for deployment...")
    engine.export(
        model=model,
        export_type=ExportType.TORCH,  # <--- FIXED: Using ExportType
        export_root=item_output_dir
    )

    print(f"Testing model against defective products for '{item_name}'...")
    engine.test(datamodule=datamodule, model=model)

    print(f"Training Complete! Check: {item_output_dir}")
    
    # Return the exact path where the .pt file is saved
    return os.path.join(item_output_dir, "weights", "torch", "model.pt")

if __name__ == "__main__":
    LOCAL_MVTEC_ROOT = r"C:/Users/shikh/Downloads/mvtec_anomaly_detection"
    LOCAL_OUTPUTS = r"C:/Users/shikh/OneDrive/Desktop/Computer Vision/CaughtIn4K/inspection_model_outputs"
    ITEM_TO_TRAIN = "bottle" 

    if os.path.exists(LOCAL_MVTEC_ROOT):
        train_local_item_model(
            mvtec_dataset_path=LOCAL_MVTEC_ROOT, 
            item_name=ITEM_TO_TRAIN,
            base_output_dir=LOCAL_OUTPUTS
        )
    else:
        print(f"Error: The MVTec dataset path does not exist: {LOCAL_MVTEC_ROOT}")
        