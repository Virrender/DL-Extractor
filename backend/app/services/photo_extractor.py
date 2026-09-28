"""
Portrait Photo Extraction Layer.

Runs after orientation normalization and before OCR/extraction. Locates the
cardholder's photo on an ID document via face detection, crops a padded
region around it, and compresses the result to a small Base64-ready payload.

Known limitations (real, not hypothetical):
- Uses OpenCV's bundled Haar Cascade frontal-face detector, not a deep
  learning model — keeps this dependency-free and fast on CPU, but it is
  less accurate than modern detectors on low-quality scans, extreme angles,
  or partially obscured photos. Expect some misses on poor photos.
- The crop is expanded from the detected face box using fixed multipliers
  to approximate typical ID-photo framing (head + shoulders). Actual card
  layouts vary, so this is an approximation, not a pixel-exact crop of the
  printed photo box.
- Returns None (not a wrong/empty crop) when no face is confidently
  detected — callers should surface this as a warning, not fabricate data.
"""

import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

TARGET_MIN_BYTES = 10 * 1024
TARGET_MAX_BYTES = 30 * 1024

# Refined for exact passport-style boundaries (no extra massive spaces)
# Haar Cascade finds the inner face. We pad just enough for hair and neck.
HORIZONTAL_MARGIN_RATIO = 0.35  # Reduced from 0.9 (Tight sides)
TOP_MARGIN_RATIO = 0.40         # Reduced from 0.8 (Enough for hair/turbans)
BOTTOM_MARGIN_RATIO = 0.65      # Reduced from 1.3 (Enough for neck/upper shoulders)


def _detect_largest_face(cv_gray: np.ndarray):
    """
    Attempts to detect the face using progressively relaxed parameters and 
    contrast enhancement to overcome holograms, watermarks, and flat lighting.
    """
    # 1. Enhance contrast (forces facial shadows to pop out against watermarks)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_gray = clahe.apply(cv_gray)

    # PASS 1: Strict detection on enhanced image (Best quality)
    faces = _FACE_CASCADE.detectMultiScale(
        enhanced_gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )

    # PASS 2: Relaxed parameters (Helps with tilted or washed-out faces)
    if len(faces) == 0:
        faces = _FACE_CASCADE.detectMultiScale(
            enhanced_gray, scaleFactor=1.05, minNeighbors=3, minSize=(50, 50)
        )

    # PASS 3: Desperation pass on the original un-enhanced image 
    # (Just in case the contrast enhancer blew out a very bright photo)
    if len(faces) == 0:
        faces = _FACE_CASCADE.detectMultiScale(
            cv_gray, scaleFactor=1.05, minNeighbors=3, minSize=(50, 50)
        )

    if len(faces) == 0:
        return None

    # Return the largest face found by area to avoid ghost images/background noise
    return max(faces, key=lambda f: f[2] * f[3])


def _crop_with_margin(img: Image.Image, face_box) -> Image.Image:
    x, y, w, h = face_box
    img_w, img_h = img.size

    left = max(0, int(x - w * HORIZONTAL_MARGIN_RATIO))
    right = min(img_w, int(x + w + w * HORIZONTAL_MARGIN_RATIO))
    top = max(0, int(y - h * TOP_MARGIN_RATIO))
    bottom = min(img_h, int(y + h + h * BOTTOM_MARGIN_RATIO))

    # Safety clamp to ensure we don't accidentally invert coordinates
    if right <= left or bottom <= top:
        return img.crop((x, y, x + w, y + h))

    return img.crop((left, top, right, bottom))


def _compress_to_target(img: Image.Image, min_bytes: int = TARGET_MIN_BYTES, max_bytes: int = TARGET_MAX_BYTES) -> bytes:
    """
    Iteratively adjusts JPEG quality (and resolution if needed) until the
    encoded size falls within [min_bytes, max_bytes]. Falls back to the
    closest achievable size if the exact range can't be hit.
    """
    img = img.convert("RGB")
    quality = 90
    best_bytes = None
    best_diff = float("inf")

    for _attempt in range(12):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        size = buf.tell()

        if min_bytes <= size <= max_bytes:
            return buf.getvalue()

        diff = min(abs(size - min_bytes), abs(size - max_bytes))
        if diff < best_diff:
            best_diff = diff
            best_bytes = buf.getvalue()

        if size > max_bytes:
            if quality > 25:
                quality -= 10
            else:
                w, h = img.size
                img = img.resize((max(1, int(w * 0.85)), max(1, int(h * 0.85))), Image.Resampling.BICUBIC)
        else:
            if quality < 95:
                quality += 5
            else:
                break

    return best_bytes


def extract_portrait_photo(img: Image.Image) -> Optional[bytes]:
    """
    Detects and crops the cardholder's photo from an orientation-normalized
    document image. Returns compressed JPEG bytes (~10-30KB), or None if no
    face could be confidently detected.
    """
    try:
        gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        face_box = _detect_largest_face(gray)
        if face_box is None:
            return None

        cropped = _crop_with_margin(img, face_box)
        return _compress_to_target(cropped)
    except Exception as e:
        logger.warning(f"Photo extraction failed: {e}")
        return None