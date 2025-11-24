import os

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from client_triton import TritonClient
from hallucination import detect_hallucination
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/translate")
def translate(req: TranslateReq):
    """Synchronous translation - returns result immediately via Triton with hallucination detection"""
    # Preprocess: split into sentences
    sentences = preprocess(req.text)
    outputs = []
    model = f"opus-mt-{req.source_lang}-{req.target_lang}"

    # Translate each sentence with hallucination detection
    for sentence in sentences:
        translated = triton.forward(model, sentence)

        # Check for hallucination
        if detect_hallucination(sentence, translated, src_lang=req.source_lang):
            # Fallback: truncate to 30 tokens and retry
            cleaned = " ".join(sentence.split()[:30])
            translated = triton.forward(model, cleaned)

        outputs.append(translated)

    # Postprocess and join sentences
    result = postprocess(" ".join(outputs))

    return {"translation": result}
