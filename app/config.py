import os

from dotenv import load_dotenv

load_dotenv()


def _set_default(key, default):
    return os.environ.get(key, "").strip() or default


def azure_config():
    endpoint = _set_default("AZURE_CONTENT_SAFETY_ENDPOINT", "")
    key = _set_default("AZURE_CONTENT_SAFETY_KEY", "")
    return {"configured": bool(endpoint and key), "endpoint": endpoint, "key": key}


def aws_config():
    return {
        "configured": bool(
            _set_default("AWS_ACCESS_KEY_ID", "")
            and _set_default("AWS_SECRET_ACCESS_KEY", "")
        ),
        "access_key_id": _set_default("AWS_ACCESS_KEY_ID", ""),
        "secret_access_key": _set_default("AWS_SECRET_ACCESS_KEY", ""),
        "region": _set_default("AWS_REGION", "us-east-1"),
    }


def gcp_config():
    path = _set_default("GCP_SERVICE_ACCOUNT_JSON", "")
    return {
        "configured": bool(path) and os.path.isfile(path),
        "credentials_path": path,
    }


DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-20b:free"


def llm_config():
    key = _set_default("OPENROUTER_API_KEY", "")
    model = _set_default("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
    return {
        "configured": bool(key),
        "api_key": key,
        "model": model,
    }


def configured_providers():
    return [
        name
        for name, cfg in (
            ("azure", azure_config()),
            ("aws", aws_config()),
            ("gcp", gcp_config()),
        )
        if cfg["configured"]
    ]
