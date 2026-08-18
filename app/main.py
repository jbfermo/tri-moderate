import functools
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import configured_providers
from app.image_utils import ImageTooLargeError, prepare_image
from app.llm import summarize_verdict
from app.providers.aws_provider import AWSProvider
from app.providers.azure_provider import AzureProvider
from app.providers.base import ProviderError
from app.providers.gcp_provider import GCPProvider

app = FastAPI(title="TriModerate")

STATIC_DIR = Path(__file__).parent / "static"


def build_registry():
    return {
        "azure": AzureProvider,
        "aws": AWSProvider,
        "gcp": GCPProvider,
    }


@functools.lru_cache(maxsize=None)
def get_provider(name: str):
    registry = build_registry()
    if name not in registry:
        return None
    return registry[name]()


def validate_image(upload: UploadFile) -> bytes:
    data = upload.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    try:
        return prepare_image(data)
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not process image: {exc}"
        ) from exc


def moderate_with(name: str, image_bytes: bytes):
    try:
        provider = get_provider(name)
        if provider is None:
            raise HTTPException(
                status_code=404, detail=f"Unknown provider '{name}'"
            )
        result = provider.moderate_image(image_bytes)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"provider": name, **result}


def aggregate(results: dict) -> dict:
    errored = [name for name, r in results.items() if r.get("error")]
    flagging = [name for name, r in results.items() if r.get("flagged")]
    if flagging:
        return {"verdict": "FLAGGED", "flagging_providers": flagging}
    if len(results) == len(errored):
        return {"verdict": "ERROR", "flagging_providers": []}
    return {"verdict": "SAFE", "flagging_providers": []}


def run_all(image_bytes: bytes) -> dict:
    available = configured_providers()
    if not available:
        raise HTTPException(
            status_code=400,
            detail="No cloud credentials configured. See README.md for setup.",
        )

    results = {}
    for name in build_registry():
        try:
            provider = get_provider(name)
            results[name] = provider.moderate_image(image_bytes)
        except ProviderError as exc:
            results[name] = {"error": str(exc)}
    return {"results": results, "summary": aggregate(results)}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/moderate/all")
async def moderate_all(file: UploadFile = File(...)):
    image_bytes = validate_image(file)
    return JSONResponse(run_all(image_bytes))


@app.post("/moderate/explain")
async def moderate_explain(file: UploadFile = File(...)):
    image_bytes = validate_image(file)
    outcome = run_all(image_bytes)
    try:
        outcome["explanation"] = summarize_verdict(outcome)
    except ProviderError as exc:
        outcome["explanation"] = None
        outcome["explanation_error"] = str(exc)
    return JSONResponse(outcome)


@app.post("/moderate/{provider}")
async def moderate_single(provider: str, file: UploadFile = File(...)):
    image_bytes = validate_image(file)
    return JSONResponse(moderate_with(provider, image_bytes))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
