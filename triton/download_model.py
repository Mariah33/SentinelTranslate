"""Download and convert OPUS-MT models to ONNX format for Triton.

This script downloads all 41 OPUS-MT language pair models from Helsinki-NLP
and converts them to ONNX format suitable for Triton Inference Server.
"""

from pathlib import Path

from optimum.exporters.onnx import main_export

LANGUAGES = {
    "ar", "bg", "bn", "cs", "da", "de", "el", "es", "et", "fa",
    "fi", "fr", "he", "hi", "hr", "hu", "id", "it", "ja", "ko",
    "lt", "lv", "ms", "nl", "no", "pl", "pt", "ro", "ru", "sk",
    "sl", "sr", "sv", "ta", "te", "th", "tr", "uk", "ur", "vi", "zh",
}

total = len(LANGUAGES)
print(f"Starting conversion of {total} OPUS-MT models...")
print("This will download ~12GB and may take 30-60 minutes.\n")

failed = []
succeeded = []

for idx, lang in enumerate(sorted(LANGUAGES), 1):
    model_name = f"opus-mt-{lang}-en"
    output_dir = Path(f"model-repository/{model_name}/1")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{idx}/{total}] Converting Helsinki-NLP/{model_name}...")

    try:
        main_export(
            model_name_or_path=f"Helsinki-NLP/{model_name}",
            output=output_dir,
            task="text2text-generation",
        )
        succeeded.append(model_name)
        print(f"  ✓ Success: {output_dir}/model.onnx")
    except Exception as e:
        failed.append((model_name, str(e)))
        print(f"  ✗ Failed: {e}")
        continue

print(f"\n{'='*60}")
print(f"Conversion complete!")
print(f"  Succeeded: {len(succeeded)}/{total}")
print(f"  Failed: {len(failed)}/{total}")

if failed:
    print(f"\nFailed models:")
    for model, error in failed:
        print(f"  - {model}: {error[:80]}...")
else:
    print(f"\n✓ All models converted successfully!")
    print(f"  Total size: ~12GB")
    print(f"\nNext steps:")
    print(f"  1. Start Triton: docker-compose up triton")
    print(f"  2. Test a model: curl http://localhost:8000/v2/models/opus-mt-fr-en")