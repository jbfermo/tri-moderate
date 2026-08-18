import json
import time

from openai import OpenAI

from app.config import llm_config
from app.providers.base import ProviderError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 10

SYSTEM_PROMPT_V1 = (
    "You are a content-moderation decision assistant for a photo-sharing app. "
    "You receive the output of an automated image-moderation system that ran "
    "the same image through three cloud providers (Azure AI Content Safety, "
    "AWS Rekognition, and GCP Vision SafeSearch). "
    "Write a concise, plain-English explanation (2-4 sentences) of the overall "
    "verdict. If the image was flagged, name the specific categories and which "
    "providers raised them, and recommend one action: BLOCK, REVIEW, or ALLOW. "
    "Be factual and neutral; do not speculate about the image beyond what the "
    "moderation results state. Never mention that you are an AI."
)

USER_PROMPT_V1 = (
    "Here are the moderation results:\n\n{payload}\n\n"
    "Give the explanation and recommended action."
)

MODEL_TEMPERATURE = 0.2


def build_messages(results: dict) -> list[dict]:
    payload = json.dumps(results, indent=2)
    return [
        {"role": "system", "content": SYSTEM_PROMPT_V1},
        {"role": "user", "content": USER_PROMPT_V1.format(payload=payload)},
    ]


def summarize_verdict(results: dict) -> str:
    cfg = llm_config()
    if not cfg["configured"]:
        raise ProviderError(
            "LLM is not configured. Set OPENROUTER_API_KEY in .env"
        )

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=cfg["api_key"],
        default_headers={
            "HTTP-Referer": "https://github.com/jesella/tri-moderate",
            "X-Title": "TriModerate",
        },
    )
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=build_messages(results),
            temperature=MODEL_TEMPERATURE,
            max_tokens=300,
        )
    except Exception as exc:
        if "429" in str(exc) and MAX_RETRIES > 0:
            for attempt in range(1, MAX_RETRIES + 1):
                time.sleep(RETRY_SLEEP_SECONDS)
                try:
                    response = client.chat.completions.create(
                        model=cfg["model"],
                        messages=build_messages(results),
                        temperature=MODEL_TEMPERATURE,
                        max_tokens=300,
                    )
                    break
                except Exception as retry_exc:
                    if attempt == MAX_RETRIES or "429" not in str(retry_exc):
                        raise ProviderError(
                            f"LLM request failed: {retry_exc}"
                        ) from retry_exc
        else:
            raise ProviderError(f"LLM request failed: {exc}") from exc

    content = response.choices[0].message.content
    return content.strip() if content else ""
