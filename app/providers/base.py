from abc import ABC, abstractmethod


class ProviderError(Exception):
    pass


class Provider(ABC):
    """Base class for cloud image-moderation providers.

    Subclasses implement `moderate_image`, which receives raw image bytes and
    returns a normalized moderation result dict:

        {
            "flagged": bool,          # True if any category crossed threshold
            "categories": [
                {
                    "category": str,      # top-level category (e.g. "Violence")
                    "label": str,         # specific label / description
                    "confidence": float,  # severity/likelihood normalized to 0-1
                    "flagged": bool,      # this category crossed threshold
                }
            ],
        }
    """

    name = "base"

    @abstractmethod
    def moderate_image(self, image_bytes: bytes) -> dict:
        raise NotImplementedError

    def _result(self, categories):
        return {
            "flagged": any(c["flagged"] for c in categories),
            "categories": categories,
        }

    def _category(self, category, label=None, confidence=0.0, flagged=False):
        return {
            "category": str(category),
            "label": str(label if label is not None else category),
            "confidence": round(float(confidence), 4),
            "flagged": bool(flagged),
        }
