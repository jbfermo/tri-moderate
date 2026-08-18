import io

from PIL import Image

MAX_DIMENSION = 1024
MAX_OUTPUT_BYTES = 3_500_000
MAX_INPUT_BYTES = 20_000_000


class ImageTooLargeError(Exception):
    pass


def prepare_image(image_bytes: bytes) -> bytes:
    """Resize/re-encode an image so it fits every provider's input limits."""
    if len(image_bytes) > MAX_INPUT_BYTES:
        raise ImageTooLargeError(
            f"Image is {len(image_bytes)} bytes; maximum allowed is {MAX_INPUT_BYTES}"
        )

    image = Image.open(io.BytesIO(image_bytes))
    image.load()
    image = image.convert("RGB")
    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    return _encode_under_limit(image)


def _encode_under_limit(image: Image.Image) -> bytes:
    data = b""
    for quality in (85, 70, 55, 40):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= MAX_OUTPUT_BYTES:
            break
    return data