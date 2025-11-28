import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from client_triton import TritonClient
from hallucination import detect_hallucination
from language_codes import iso_to_flores
from postprocessing import postprocess
from preprocessing import preprocess

app = FastAPI()

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Use environment variables for configuration (with fallback for local dev)
TRITON_URL = os.environ.get("TRITON_URL", "triton:8000")

triton = TritonClient(TRITON_URL)


class TranslateReq(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    model: Literal["opus", "nllb"] = "opus"  # Default to OPUS-MT for backward compatibility


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/translate")
def translate(req: TranslateReq):
    """Synchronous translation - returns result immediately via Triton with hallucination detection.

    Supports both OPUS-MT and NLLB-200 models:
    - OPUS-MT: Separate models per language pair (opus-mt-{src}-{tgt})
    - NLLB-200: Single model for all language pairs (nllb-200-distilled-600m)
    """
    # Preprocess: split into sentences using language-aware SBD
    sentences = preprocess(req.text, lang_code=req.source_lang)
    outputs = []

    # Determine model name and prepare language codes
    if req.model == "nllb":
        model_name = "nllb-200-distilled-600m"
        # Convert ISO 639-1 codes to FLORES-200 format for NLLB
        try:
            src_flores = iso_to_flores(req.source_lang)
            tgt_flores = iso_to_flores(req.target_lang)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        # OPUS-MT: model name includes language pair
        model_name = f"opus-mt-{req.source_lang}-{req.target_lang}"
        src_flores = None
        tgt_flores = None

    # Translate each sentence with hallucination detection
    for sentence in sentences:
        translated = triton.translate(
            model=model_name,
            text=sentence,
            src_lang=src_flores,
            tgt_lang=tgt_flores,
        )

        # Check for hallucination
        if detect_hallucination(sentence, translated, src_lang=req.source_lang):
            # Fallback: truncate to 30 tokens and retry
            cleaned = " ".join(sentence.split()[:30])
            translated = triton.translate(
                model=model_name,
                text=cleaned,
                src_lang=src_flores,
                tgt_lang=tgt_flores,
            )

        outputs.append(translated)

    # Postprocess and join sentences
    result = postprocess(" ".join(outputs))

    return {"translation": result}
