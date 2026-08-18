from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeImageOptions, ImageCategory, ImageData
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from app.config import azure_config
from app.providers.base import Provider, ProviderError

FLAG_SEVERITY = 2
MAX_SEVERITY = 6


class AzureProvider(Provider):
    name = "azure"

    def __init__(self):
        cfg = azure_config()
        if not cfg["configured"]:
            raise ProviderError(
                "Azure is not configured. Set AZURE_CONTENT_SAFETY_ENDPOINT and "
                "AZURE_CONTENT_SAFETY_KEY in .env"
            )
        self.client = ContentSafetyClient(
            endpoint=cfg["endpoint"],
            credential=AzureKeyCredential(cfg["key"]),
        )

    def moderate_image(self, image_bytes: bytes) -> dict:
        try:
            response = self.client.analyze_image(
                AnalyzeImageOptions(image=ImageData(content=image_bytes))
            )
        except HttpResponseError as exc:
            raise ProviderError(f"Azure request failed: {exc}") from exc

        categories = []
        for item in response.categories_analysis or []:
            severity = int(item.severity or 0)
            categories.append(
                self._category(
                    category=item.category,
                    confidence=severity / MAX_SEVERITY,
                    flagged=severity >= FLAG_SEVERITY,
                )
            )
        return self._result(categories)
