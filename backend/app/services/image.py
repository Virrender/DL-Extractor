import base64
import binascii

import cv2
import numpy as np


def decode_base64_image(image_base64: str) -> np.ndarray:
    """
    Decode a Base64-encoded image into an OpenCV image.
    """

    try:
        image_bytes = base64.b64decode(
            image_base64,
            validate=True
        )
    except (binascii.Error, ValueError):
        raise ValueError("Invalid Base64 image data")

    if not image_bytes:
        raise ValueError("Image data is empty")

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError("Decoded data is not a valid image")

    return image