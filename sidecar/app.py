from uuid import uuid4

from celery import Celery
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from client_triton import TritonClient

app = FastAPI()

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

celery_app = Celery("translator", broker="redis://redis:6379/0", backend="redis://redis:6379/1")
triton = TritonClient("triton:8000")


class Req(BaseModel):
    text: str
    source_lang: str
    target_lang: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/translate")
def translate(req: Req):
    job_id = str(uuid4())
    celery_app.send_task("tasks.translate", args=[job_id, req.text, req.source_lang, req.target_lang])
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    r = celery_app.AsyncResult(job_id)
    return {"status": r.status, "result": r.result}
