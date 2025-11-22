# Triton Model Repository

This directory contains the NVIDIA Triton Inference Server model repository for OPUS-MT translation models.

## Structure

Each model follows the Triton naming convention:
```
model-repository/
└── opus-mt-{source_lang}-en/
    ├── config.pbtxt          # Triton model configuration
    ├── README.txt            # Model placement instructions
    └── 1/
        └── model.onnx        # ONNX model file (you need to add this)
```

## Supported Languages

The repository is configured for 41 language pairs, all translating to English:
- Arabic (ar), Bulgarian (bg), Bengali (bn), Czech (cs), Danish (da)
- German (de), Greek (el), Spanish (es), Estonian (et), Persian (fa)
- Finnish (fi), French (fr), Hebrew (he), Hindi (hi), Croatian (hr)
- Hungarian (hu), Indonesian (id), Italian (it), Japanese (ja), Korean (ko)
- Lithuanian (lt), Latvian (lv), Malay (ms), Dutch (nl), Norwegian (no)
- Polish (pl), Portuguese (pt), Romanian (ro), Russian (ru), Slovak (sk)
- Slovenian (sl), Serbian (sr), Swedish (sv), Tamil (ta), Telugu (te)
- Thai (th), Turkish (tr), Ukrainian (uk), Urdu (ur), Vietnamese (vi)
- Chinese (zh)

## Adding Models

### Option 1: Download Pre-converted ONNX Models

If you have ONNX versions of OPUS-MT models:

```bash
# Example: Add French-to-English model
mkdir -p opus-mt-fr-en/1
cp /path/to/opus-mt-fr-en.onnx opus-mt-fr-en/1/model.onnx
```

### Option 2: Convert from HuggingFace

Convert PyTorch models to ONNX format:

```bash
# Install dependencies
pip install transformers onnx optimum[exporters]

# Convert model (example for French)
python -m optimum.exporters.onnx \
  --model Helsinki-NLP/opus-mt-fr-en \
  --task text2text-generation \
  opus-mt-fr-en/1/

# Rename to expected filename
mv opus-mt-fr-en/1/model.onnx opus-mt-fr-en/1/model.onnx
```

### Option 3: Bulk Conversion Script

```python
# convert_models.py
from optimum.exporters.onnx import main_export
from pathlib import Path

LANGUAGES = ["fr", "de", "es", "it", "pt", "ru", "ja", "zh"]

for lang in LANGUAGES:
    model_name = f"opus-mt-{lang}-en"
    output_dir = Path(f"model-repository/{model_name}/1")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting {model_name}...")
    main_export(
        f"Helsinki-NLP/{model_name}",
        output=output_dir,
        task="text2text-generation"
    )
```

## Model Configuration

Each model's `config.pbtxt` specifies:
- **Platform**: `onnxruntime_onnx` (CPU/GPU inference)
- **Max batch size**: 8 (process up to 8 sentences in parallel)
- **Input**: `INPUT_TEXT` (string array)
- **Output**: `OUTPUT_TEXT` (string array)

To modify model settings, edit `config.pbtxt` in the model directory.

## Verifying Models

Check if Triton can load your models:

```bash
# Start Triton (from project root)
docker-compose up triton

# Check model status
curl http://localhost:8000/v2/models/opus-mt-fr-en

# Test inference
curl -X POST http://localhost:8000/v2/models/opus-mt-fr-en/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "name": "INPUT_TEXT",
        "datatype": "BYTES",
        "shape": [1],
        "data": ["Bonjour le monde"]
      }
    ]
  }'
```

## Troubleshooting

### Model not loading
- Check that `1/model.onnx` exists in the model directory
- Verify ONNX model is compatible with onnxruntime
- Check Triton logs: `docker-compose logs triton`

### Out of memory
- Reduce batch size in `config.pbtxt`
- Deploy fewer models at once
- Increase GPU memory allocation

### CPU vs GPU
- **GPU**: Requires NVIDIA GPU and `nvidia-docker` runtime
- **CPU**: Use `docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up`

## Performance Tips

1. **Use GPU when available**: 10-100x faster than CPU
2. **Batch processing**: Group sentences for better throughput
3. **Model quantization**: Reduce model size with INT8/FP16
4. **Dynamic batching**: Enable in `config.pbtxt` for automatic batching
