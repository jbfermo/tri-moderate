import io
import random
import warnings
from unittest.mock import MagicMock, patch

import PIL.Image

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.llm import build_messages
from app.main import app
from app.providers.base import ProviderError

client = TestClient(app)


def make_png_bytes():
    buf = io.BytesIO()
    PIL.Image.new("RGB", (64, 64), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_ui_served():
    assert client.get("/").status_code == 200


def test_no_creds_error():
    with patch("app.main.configured_providers", return_value=[]):
        res = client.post(
            "/moderate/all", files={"file": ("img.png", make_png_bytes(), "image/png")}
        )
    assert res.status_code == 400
    assert "credentials" in res.json()["detail"].lower()


def test_unknown_provider_404():
    res = client.post(
        "/moderate/nope", files={"file": ("img.png", make_png_bytes(), "image/png")}
    )
    assert res.status_code == 404


def test_azure_unconfigured_400():
    with patch(
        "app.main.get_provider",
        side_effect=ProviderError(
            "Azure is not configured. Set AZURE_CONTENT_SAFETY_ENDPOINT and "
            "AZURE_CONTENT_SAFETY_KEY in .env"
        ),
    ):
        res = client.post(
            "/moderate/azure",
            files={"file": ("img.png", make_png_bytes(), "image/png")},
        )
    assert res.status_code == 400
    assert "Azure" in res.json()["detail"]


def test_empty_file_400():
    res = client.post(
        "/moderate/all", files={"file": ("img.png", b"", "image/png")}
    )
    assert res.status_code == 400
    assert "Empty" in res.json()["detail"]


def test_full_flow_flagged():
    class FakeAWS:
        name = "aws"

        def moderate_image(self, image_bytes):
            return {
                "flagged": True,
                "categories": [
                    {
                        "category": "Violence",
                        "label": "Weapon Violence",
                        "confidence": 0.97,
                        "flagged": True,
                    }
                ],
            }

    def fake_get(name):
        if name == "aws":
            return FakeAWS()
        raise ProviderError(f"{name} is not configured")

    with patch("app.main.configured_providers", return_value=["aws"]):
        with patch("app.main.get_provider", side_effect=fake_get):
            res = client.post(
                "/moderate/all",
                files={"file": ("img.png", make_png_bytes(), "image/png")},
            )

    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["verdict"] == "FLAGGED"
    assert body["summary"]["flagging_providers"] == ["aws"]
    assert body["results"]["aws"]["flagged"] is True
    assert "error" in body["results"]["azure"]
    assert "error" in body["results"]["gcp"]


def test_full_flow_safe():
    class FakeAWS:
        name = "aws"

        def moderate_image(self, image_bytes):
            return {"flagged": False, "categories": []}

    def fake_get(name):
        if name == "aws":
            return FakeAWS()
        raise ProviderError(f"{name} is not configured")

    with patch("app.main.configured_providers", return_value=["aws"]):
        with patch("app.main.get_provider", side_effect=fake_get):
            res = client.post(
                "/moderate/all",
                files={"file": ("img.png", make_png_bytes(), "image/png")},
            )

    assert res.status_code == 200
    assert res.json()["summary"]["verdict"] == "SAFE"
    assert res.json()["summary"]["flagging_providers"] == []


def test_all_errors_gives_error_verdict():
    def fake_get(name):
        raise ProviderError(f"{name} is not configured")

    with patch("app.main.configured_providers", return_value=["azure"]):
        with patch("app.main.get_provider", side_effect=fake_get):
            res = client.post(
                "/moderate/all",
                files={"file": ("img.png", make_png_bytes(), "image/png")},
            )

    assert res.status_code == 200
    assert res.json()["summary"]["verdict"] == "ERROR"


def test_large_image_is_downscaled():
    received_size = {}

    class FakeGCP:
        name = "gcp"

        def moderate_image(self, image_bytes):
            received_size["bytes"] = len(image_bytes)
            return {"flagged": False, "categories": []}

    raw = bytes(random.randrange(256) for _ in range(3000 * 2000 * 3))
    big_image = PIL.Image.frombytes("RGB", (3000, 2000), raw)
    buf = io.BytesIO()
    big_image.save(buf, format="JPEG", quality=95)
    big = buf.getvalue()
    assert len(big) > 4_000_000, "fixture should be too large for Azure"

    with patch("app.main.get_provider", return_value=FakeGCP()):
        res = client.post(
            "/moderate/gcp",
            files={"file": ("big.jpg", big, "image/jpeg")},
        )

    assert res.status_code == 200
    assert received_size["bytes"] < 4_000_000


def test_single_provider_flow():
    class FakeGCP:
        name = "gcp"

        def moderate_image(self, image_bytes):
            return {
                "flagged": False,
                "categories": [
                    {"category": "violence", "label": "violence", "confidence": 0.05, "flagged": False}
                ],
            }

    with patch("app.main.get_provider", return_value=FakeGCP()):
        res = client.post(
            "/moderate/gcp",
            files={"file": ("img.png", make_png_bytes(), "image/png")},
        )

    assert res.status_code == 200
    assert res.json()["provider"] == "gcp"
    assert res.json()["flagged"] is False


def test_explain_returns_explanation():
    class FakeAWS:
        name = "aws"

        def moderate_image(self, image_bytes):
            return {
                "flagged": True,
                "categories": [
                    {"category": "Violence", "label": "Weapon Violence", "confidence": 0.97, "flagged": True}
                ],
            }

    def fake_get(name):
        if name == "aws":
            return FakeAWS()
        raise ProviderError(f"{name} is not configured")

    with patch("app.main.configured_providers", return_value=["aws"]):
        with patch("app.main.get_provider", side_effect=fake_get):
            with patch(
                "app.main.summarize_verdict", return_value="Image flagged for Violence by AWS."
            ) as mock_llm:
                res = client.post(
                    "/moderate/explain",
                    files={"file": ("img.png", make_png_bytes(), "image/png")},
                )

    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["verdict"] == "FLAGGED"
    assert body["explanation"] == "Image flagged for Violence by AWS."
    assert mock_llm.call_count == 1


def test_explain_with_llm_error():
    class FakeAWS:
        name = "aws"

        def moderate_image(self, image_bytes):
            return {"flagged": False, "categories": []}

    def fake_get(name):
        if name == "aws":
            return FakeAWS()
        raise ProviderError(f"{name} is not configured")

    with patch("app.main.configured_providers", return_value=["aws"]):
        with patch("app.main.get_provider", side_effect=fake_get):
            with patch(
                "app.main.summarize_verdict",
                side_effect=ProviderError("LLM is not configured."),
            ):
                res = client.post(
                    "/moderate/explain",
                    files={"file": ("img.png", make_png_bytes(), "image/png")},
                )

    assert res.status_code == 200
    body = res.json()
    assert body["explanation"] is None
    assert "LLM is not configured" in body["explanation_error"]


def test_prompt_template_injects_results():
    results = {
        "summary": {"verdict": "SAFE", "flagging_providers": []},
        "results": {"gcp": {"flagged": False, "categories": []}},
    }
    messages = build_messages(results)
    assert messages[0]["role"] == "system"
    assert "moderation decision assistant" in messages[0]["content"].lower()
    assert '"gcp"' in messages[1]["content"]
    assert '"SAFE"' in messages[1]["content"]


def test_llm_unconfigured_raises():
    from app.llm import summarize_verdict

    with patch("app.llm.llm_config", return_value={"configured": False}):
        try:
            summarize_verdict({"results": {}})
        except ProviderError as exc:
            assert "OPENROUTER_API_KEY" in str(exc)
        else:
            raise AssertionError("expected ProviderError")


def test_llm_uses_openrouter_client():
    from app import llm

    mock_message = MagicMock()
    mock_message.content = "  Explained.  "
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch(
        "app.llm.llm_config",
        return_value={"configured": True, "api_key": "sk-or-v1-test", "model": "some/model:free"},
    ):
        with patch("app.llm.OpenAI", return_value=mock_client) as mock_openai:
            out = llm.summarize_verdict({"results": {}})

    assert out == "Explained."
    mock_openai.assert_called_once()
    kwargs = mock_openai.call_args.kwargs
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-v1-test"
    mock_client.chat.completions.create.assert_called_once()
    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "some/model:free"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
