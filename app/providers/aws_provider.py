import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import aws_config
from app.providers.base import Provider, ProviderError

MIN_CONFIDENCE = 50.0


class AWSProvider(Provider):
    name = "aws"

    def __init__(self):
        cfg = aws_config()
        if not cfg["configured"]:
            raise ProviderError(
                "AWS is not configured. Set AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY in .env"
            )
        self.client = boto3.client(
            "rekognition",
            region_name=cfg["region"],
            aws_access_key_id=cfg["access_key_id"],
            aws_secret_access_key=cfg["secret_access_key"],
        )

    def moderate_image(self, image_bytes: bytes) -> dict:
        try:
            response = self.client.detect_moderation_labels(
                Image={"Bytes": image_bytes}, MinConfidence=MIN_CONFIDENCE
            )
        except (BotoCoreError, ClientError) as exc:
            raise ProviderError(f"AWS request failed: {exc}") from exc

        categories = []
        for label in response.get("ModerationLabels", []):
            confidence = float(label.get("Confidence") or 0.0) / 100.0
            categories.append(
                self._category(
                    category=label.get("ParentName") or label["Name"],
                    label=label.get("Name"),
                    confidence=confidence,
                    flagged=confidence >= MIN_CONFIDENCE / 100.0,
                )
            )
        return self._result(categories)
