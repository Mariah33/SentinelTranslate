# SentinelTranslate Examples

This directory contains comprehensive Jupyter notebook examples demonstrating how to use SentinelTranslate for machine translation across multiple language pairs using OPUS-MT models.

## Overview

SentinelTranslate is a distributed machine translation pipeline with built-in hallucination prevention. It uses:
- **NVIDIA Triton Inference Server** for GPU-accelerated OPUS-MT model serving
- **FastAPI Sidecar** (port 8080) for single-text translation
- **FastAPI Batch API** (port 8090) for large-scale parquet file translation
- **Celery Workers** with multi-layer safety checks (language validation, number consistency, named entity verification)

These examples will help you:
- Translate text in 10 different languages to English
- Convert and deploy OPUS-MT models to Triton
- Perform batch translations on parquet files via S3
- Understand hallucination detection mechanisms
- Optimize for performance and quality

## Prerequisites

Before running these examples, ensure your SentinelTranslate environment is running:

```bash
# Start all services (from project root)
docker-compose up -d

# Verify services are healthy
curl http://localhost:8080/health  # Sidecar API
curl http://localhost:8090/health  # Batch API
curl http://localhost:8000/v2/health/ready  # Triton Server
```

**Required Python packages** (for running notebooks):
```bash
pip install jupyter requests pandas pyarrow boto3 matplotlib
```

## Quick Start

1. **Start with a simple language pair**: Try `01_french_to_english.ipynb` to understand the basic workflow
2. **Explore edge cases**: Each notebook includes hallucination detection examples
3. **Try batch translation**: See `batch_translation/batch_s3_example.ipynb` for large-scale workflows
4. **Add new models**: Use `model_conversion/convert_opus_to_onnx.ipynb` to deploy additional language pairs

## Language Support

SentinelTranslate supports translation from the following languages to English using OPUS-MT models:

| Language | Code | OPUS-MT Model | Notebook | Script | Use Cases |
|----------|------|---------------|----------|--------|-----------|
| French | `fr` | `opus-mt-fr-en` | [01_french_to_english.ipynb](01_french_to_english.ipynb) | Latin | Business docs, customer support, news |
| Spanish | `es` | `opus-mt-es-en` | [02_spanish_to_english.ipynb](02_spanish_to_english.ipynb) | Latin | Legal documents, social media, marketing |
| German | `de` | `opus-mt-de-en` | [03_german_to_english.ipynb](03_german_to_english.ipynb) | Latin | Technical docs, research papers, automotive |
| Italian | `it` | `opus-mt-it-en` | [04_italian_to_english.ipynb](04_italian_to_english.ipynb) | Latin | Fashion, design, culinary content |
| Portuguese | `pt` | `opus-mt-pt-en` | [05_portuguese_to_english.ipynb](05_portuguese_to_english.ipynb) | Latin | Brazilian market, news, e-commerce |
| Russian | `ru` | `opus-mt-ru-en` | [06_russian_to_english.ipynb](06_russian_to_english.ipynb) | Cyrillic | News monitoring, technical content |
| Chinese | `zh` | `opus-mt-zh-en` | [07_chinese_to_english.ipynb](07_chinese_to_english.ipynb) | Logographic | E-commerce, manufacturing, research |
| Japanese | `ja` | `opus-mt-ja-en` | [08_japanese_to_english.ipynb](08_japanese_to_english.ipynb) | Mixed (Kanji/Hiragana/Katakana) | Anime, gaming, electronics, manga |
| Arabic | `ar` | `opus-mt-ar-en` | [09_arabic_to_english.ipynb](09_arabic_to_english.ipynb) | Arabic (RTL) | News, social media, government docs |
| Korean | `ko` | `opus-mt-ko-en` | [10_korean_to_english.ipynb](10_korean_to_english.ipynb) | Hangul | K-pop, entertainment, tech startups |

### Script Diversity

The language pairs above demonstrate SentinelTranslate's ability to handle:
- **Latin scripts**: French, Spanish, German, Italian, Portuguese
- **Cyrillic**: Russian
- **Logographic**: Chinese
- **Mixed scripts**: Japanese (Kanji, Hiragana, Katakana)
- **Right-to-left**: Arabic
- **Hangul**: Korean

## Directory Structure

```
examples/
├── README.md                          # This file
├── 01_french_to_english.ipynb         # French → English tutorial
├── 02_spanish_to_english.ipynb        # Spanish → English tutorial
├── 03_german_to_english.ipynb         # German → English tutorial
├── 04_italian_to_english.ipynb        # Italian → English tutorial
├── 05_portuguese_to_english.ipynb     # Portuguese → English tutorial
├── 06_russian_to_english.ipynb        # Russian → English tutorial
├── 07_chinese_to_english.ipynb        # Chinese → English tutorial
├── 08_japanese_to_english.ipynb       # Japanese → English tutorial
├── 09_arabic_to_english.ipynb         # Arabic → English tutorial
├── 10_korean_to_english.ipynb         # Korean → English tutorial
├── model_conversion/
│   ├── README.md                      # Model conversion guide
│   └── convert_opus_to_onnx.ipynb     # OPUS-MT → ONNX → Triton
└── batch_translation/
    ├── README.md                      # Batch translation guide
    ├── batch_s3_example.ipynb         # S3 parquet batch workflow
    └── sample_data.parquet            # 100+ row sample dataset
```

## What You'll Learn

### Language Translation Notebooks (01-10)

Each language-specific notebook teaches:

1. **Service Health Checks**: Verify Sidecar, Batch API, and Triton are running
2. **Single Text Translation**: Submit a translation request and poll for results
3. **Common Phrases**: Translate greetings, business phrases, technical terms
4. **Edge Cases**: Handle numbers, dates, special characters, named entities
5. **Hallucination Detection**: Examples that trigger safety checks
   - Length ratio violations (translation too long/short)
   - Repetition detection
   - Language ID mismatches
   - Number consistency failures
   - Named entity hallucinations
6. **Performance Measurement**: Measure latency and throughput
7. **Error Handling**: Handle API errors, timeouts, model unavailability

### Model Conversion Tutorial

`model_conversion/convert_opus_to_onnx.ipynb` covers:
- Downloading OPUS-MT models from Hugging Face
- Converting PyTorch models to ONNX format
- Optimizing models with quantization (INT8/FP16)
- Creating Triton model repository structure
- Writing `config.pbtxt` files
- Testing models with Triton HTTP API
- Performance benchmarking (CPU vs GPU)

### Batch Translation Tutorial

`batch_translation/batch_s3_example.ipynb` demonstrates:
- Creating parquet files with pandas
- Uploading to S3 using boto3
- Submitting batch translation jobs
- Monitoring job progress
- Downloading and analyzing results
- Error handling and retry strategies
- Cost estimation and optimization

## API Endpoints

### Sidecar API (Single Translation)

**Base URL**: `http://localhost:8080`

```python
# Submit translation
POST /translate
{
  "text": "Bonjour le monde",
  "source_lang": "fr",
  "target_lang": "en"
}
# Returns: {"job_id": "uuid4-string", "message": "Translation job submitted"}

# Check status
GET /status/{job_id}
# Returns: {"status": "SUCCESS", "result": "Hello world"}
```

### Batch API (Parquet Translation)

**Base URL**: `http://localhost:8090`

```python
# Submit batch job
POST /batch/translate
{
  "s3_bucket": "my-bucket",
  "s3_key": "input/data.parquet",
  "text_column": "content",
  "source_lang": "fr",
  "target_lang": "en",
  "output_s3_bucket": "my-bucket",  # Optional
  "output_s3_key": "output/data_en.parquet",  # Optional
  "id_column": "id"  # Optional
}
# Returns: {"job_id": "uuid4-string", "message": "Batch translation job submitted"}

# Check status
GET /batch/status/{job_id}
# Returns: {"status": "SUCCESS", "result": {...}}
```

## Hallucination Detection

SentinelTranslate uses a multi-layer safety pipeline to detect unreliable translations:

1. **Base Checks**:
   - **Length ratio**: Translation shouldn't be >2.5x longer than source
   - **Repetition**: Detects repeated tokens (score >2)

2. **Language Validation**:
   - Uses `langid` to verify source text matches declared language
   - Prevents wrong-language input from corrupting output

3. **Number Consistency**:
   - Extracts all numbers from source and target
   - Ensures no numbers are added, removed, or changed

4. **Named Entity Consistency** (NER):
   - Uses spaCy to identify persons, organizations, locations
   - Prevents hallucinated entities in translation

If ANY check fails, the sentence is truncated to 30 tokens and retranslated.

## Performance Tips

### Single Translation
- **Expected latency**: 50-200ms per sentence (CPU), 10-50ms (GPU)
- Use for real-time user-facing translations
- Consider caching frequent translations

### Batch Translation
- **Throughput**: 1000-10000 rows/minute depending on hardware
- Use for offline processing, data pipelines, analytics
- Optimize by adjusting worker concurrency
- Pre-filter data to remove empty/duplicate rows

### Model Selection
- **General purpose**: `opus-mt-{lang}-en` models work well for most content
- **Domain-specific**: Fine-tune on your corpus for specialized vocabulary
- **Quantization**: INT8 models are 4x faster with minimal quality loss

## Troubleshooting

### Services Not Running
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs sidecar
docker-compose logs worker
docker-compose logs triton

# Restart services
docker-compose restart
```

### Model Not Found
```
Error: "Model 'opus-mt-fr-en' not found"
```
**Solution**: Convert and deploy the model using `model_conversion/convert_opus_to_onnx.ipynb`

### Hallucination Detected
```
Warning: "Translation failed safety check, retrying with truncation"
```
**This is normal**: The system automatically handles unsafe translations. Check the final result.

### Job Stuck in PENDING
```
Status: "PENDING" (doesn't progress to SUCCESS)
```
**Solution**: Check Celery worker logs. Worker may be down or queue may be backed up.
```bash
docker-compose logs worker
```

## OPUS-MT Model Resources

- **Model Hub**: [Helsinki-NLP on Hugging Face](https://huggingface.co/Helsinki-NLP)
- **Paper**: [OPUS-MT — Building open translation services for the World (2020)](https://aclanthology.org/2020.eamt-1.61/)
- **Supported Languages**: 1000+ language pairs
- **License**: CC-BY-4.0 (free for commercial use)

### Adding New Language Pairs

To add a language pair not covered in these examples:

1. Find the model on Hugging Face: `Helsinki-NLP/opus-mt-{src}-{tgt}`
2. Follow `model_conversion/convert_opus_to_onnx.ipynb` to convert
3. Deploy to `triton/model-repository/opus-mt-{src}-{tgt}/`
4. Restart Triton: `docker-compose restart triton`
5. Test with the Sidecar API

Currently supported by SentinelTranslate:
- **Source languages**: fr, es, de, it, pt, ru, zh, ja, ar, ko
- **Target language**: en (English)
- **Future**: Extend to multilingual targets (en→fr, en→es, etc.)

## Contributing

Found an issue or want to add more examples?

1. **Report bugs**: Open an issue on GitHub
2. **Add notebooks**: Submit a PR with your example notebook
3. **Request languages**: Suggest new language pairs to support
4. **Share use cases**: Tell us how you're using SentinelTranslate

## Next Steps

1. **Run your first translation**: Start with `01_french_to_english.ipynb`
2. **Explore different languages**: Try notebooks with different scripts (Cyrillic, Arabic, Chinese)
3. **Deploy to production**: Use the batch API for large-scale workflows
4. **Optimize performance**: Experiment with model quantization and worker scaling
5. **Contribute**: Add support for new language pairs or improve hallucination detection

## License

These examples are provided under the same license as SentinelTranslate (see main LICENSE file).

OPUS-MT models are licensed under CC-BY-4.0 and may be used freely, including for commercial purposes.

---

**Need help?** Check the main [SentinelTranslate README](../README.md) or open an issue on GitHub.
