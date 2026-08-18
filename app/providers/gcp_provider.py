from google.cloud import vision
from google.cloud.vision import Likelihood

from app.config import gcp_config
from app.providers.base import Provider, ProviderError

LIKELIHOOD_CONFIDENCE = {
    Likelihood.UNKNOWN: 0.0,
    Likelihood.VERY_UNLIKELY: 0.05,
    Likelihood.UNLIKELY: 0.25,
    Likelihood.POSSIBLE: 0.5,
    Likelihood.LIKELY: 0.75,
    Likelihood.VERY_LIKELY: 0.95,
}
FLAG_MIN = LIKELIHOOD_CONFIDENCE[Likelihood.POSSIBLE]

SAFE_SEARCH_ATTRS = ("adult", "spoof", "medical", "violence", "racy")


class GCPProvider(Provider):
    name = "gcp"

    def __init__(self):
        cfg = gcp_config()
        if not cfg["configured"]:
            raise ProviderError(
                "GCP is not configured. Set GCP_SERVICE_ACCOUNT_JSON in .env "
                "to the path of your service-account key file"
            )
        self.client = vision.ImageAnnotatorClient.from_service_account_file(
            cfg["credentials_path"]
        )

    def moderate_image(self, image_bytes: bytes) -> dict:
        try:
            image = vision.Image(content=image_bytes)
            response = self.client.safe_search_detection(image=image)
        except Exception as exc:
            raise ProviderError(f"GCP request failed: {exc}") from exc

        if response.error.message:
            raise ProviderError(f"GCP returned an error: {response.error.message}")

        safe = response.safe_search_annotation
        categories = []
        for attr in SAFE_SEARCH_ATTRS:
            likelihood = getattr(safe, attr, Likelihood.UNKNOWN)
            confidence = LIKELIHOOD_CONFIDENCE.get(likelihood, 0.0)
            categories.append(
                self._category(
                    category=attr,
                    confidence=confidence,
                    flagged=confidence >= FLAG_MIN,
                )
            )
        return self._result(categories)
