# Triton Model Repository

This directory contains the NVIDIA Triton Inference Server model repository for translation models:
- **OPUS-MT**: 41 language pairs → English (specialized models, ~300MB each)
- **NLLB-200**: 200+ languages any-to-any (unified model, ~1.2GB)

## Quick Start

Download models using the provided Makefile:

```bash
# Install dependencies
make install

# Download OPUS-MT models (41 models, ~12GB, 30-60 min)
make download-opus

# Download NLLB-200 model (~1.2GB, 10-15 min)
make download-nllb
```

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

### Recommended: Automated Scripts (Easiest)

Use the provided scripts to download and convert models automatically:

```bash
# Install dependencies
make install

# Download all OPUS-MT models (41 models, ~12GB)
make download-opus

# Download NLLB-200 model (~1.2GB)
make download-nllb
```

The scripts handle:
- ✅ Downloading models from Hugging Face
- ✅ Converting PyTorch models to ONNX format
- ✅ Placing files in correct Triton directory structure
- ✅ Error handling and progress reporting

### Manual: Convert Individual Models

If you want to convert specific models manually:

```bash
# Install dependencies
uv sync

# Convert a single OPUS-MT model (e.g., French)
uv run python -c "
from optimum.exporters.onnx import main_export
from pathlib import Path

model = 'Helsinki-NLP/opus-mt-fr-en'
output = Path('model-repository/opus-mt-fr-en/1')
output.mkdir(parents=True, exist_ok=True)

main_export(model, output=output, task='text2text-generation')
"
```

### Pre-converted ONNX Models

If you already have ONNX models:

```bash
# Example: Add French-to-English model
mkdir -p model-repository/opus-mt-fr-en/1
cp /path/to/model.onnx model-repository/opus-mt-fr-en/1/model.onnx
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
## Dependencies

The model download scripts require:
- Python 3.10+
- UV package manager
- ~15GB disk space (for all OPUS-MT models + NLLB)
- Internet connection for downloading from Hugging Face

Installed automatically via `make install`:
- optimum 1.27.0 (ONNX export)
- transformers 4.53.3 (model loading)
- torch 2.2.2 (PyTorch backend)
- numpy 1.26.4 (array operations)
- onnx 1.15+ (ONNX format support)
- sentencepiece 0.1.99+ (tokenization)

## Troubleshooting

### Import Error: optimum.exporters.onnx

**Error**: `ModuleNotFoundError: No module named 'optimum.exporters.onnx'`

**Solution**: Ensure you're using optimum 1.x (not 2.x):
```bash
make install  # Installs pinned compatible versions
```

### NumPy Version Conflict

**Error**: `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`

**Solution**: Dependencies are pinned to numpy<2.0 in pyproject.toml. Run:
```bash
uv sync  # Reinstalls with correct numpy version
```

### Out of Memory

**Error**: Download crashes or system becomes unresponsive

**Solution**: Models are downloaded sequentially to avoid memory issues. If problems persist:
- Download models one at a time manually
- Use `download-nllb` instead of `download-opus` (single 1.2GB vs 12GB total)
- Increase system swap space

### Connection Timeout

**Error**: `HTTPError` or `Connection refused` from Hugging Face

**Solution**:
```bash
# Retry with increased timeout
export HF_HUB_DOWNLOAD_TIMEOUT=300
make download-opus
```
