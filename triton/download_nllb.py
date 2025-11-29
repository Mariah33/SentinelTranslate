"""Download and convert NLLB-200-distilled-600M model to ONNX format for Triton.

This script downloads the Facebook NLLB-200-distilled-600M model from Hugging Face
and converts it to ONNX format suitable for Triton Inference Server.
"""

from pathlib import Path

from optimum.exporters.onnx import main_export

# Model configuration
MODEL_NAME = "facebook/nllb-200-distilled-600M"
OUTPUT_DIR = Path("model-repository/nllb-200-distilled-600m/1")

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Downloading and converting {MODEL_NAME}...")
print(f"Output directory: {OUTPUT_DIR}")
print("This may take 10-15 minutes depending on your connection...")

try:
    main_export(
        model_name_or_path=MODEL_NAME,
        output=OUTPUT_DIR,
        task="translation",  # or "text2text-generation"
    )
    print(f"\n✓ Successfully converted {MODEL_NAME} to ONNX!")
    print(f"  Model saved to: {OUTPUT_DIR}/model.onnx")
    print("\nNext steps:")
    print(f"  1. Verify the model file exists: ls -lh {OUTPUT_DIR}/")
    print("  2. Start Triton and test the model")
except Exception as e:
    print(f"\n✗ Error converting model: {e}")
    print("\nTroubleshooting:")
    print("  - Ensure you have enough disk space (~1.2GB)")
    print("  - Check your internet connection")
    print("  - Try running: uv sync --reinstall")
    raise
