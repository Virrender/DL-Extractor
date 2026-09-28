"""
Generic File Handling and Preprocessing Layer.

Responsibilities:
- Read and validate uploaded front/back image files directly (multipart
  uploads only -- no Base64, no PDF; per the current API contract, only
  a 'front' image is required and an optional 'back' image is accepted).
- Detect file signatures via magic bytes.
- Enforce memory safety limits and bounds.
- Output a generic `NormalizedPage` working structure for OCR.

Note: orientation/perspective/skew normalization happens inside
ocr_engine.py's process_page(), using PaddleOCR's own built-in
document-orientation and unwarping models -- not here.
"""

import io
import math
from dataclasses import dataclass
from typing import Literal, List, Tuple, Optional
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

MAX_IMAGE_WIDTH = 1400
MAX_IMAGE_HEIGHT = 1400
MAX_PIXELS = MAX_IMAGE_WIDTH * MAX_IMAGE_HEIGHT


class FileProcessingError(ValueError):
    """Custom exception raised for file decoding, sizing, or format errors."""
    pass


@dataclass
class NormalizedPage:
    original_image: Image.Image
    working_image: Image.Image
    page_source: Literal["front", "back"]
    page_index: int
    original_width: int
    original_height: int
    working_width: int
    working_height: int
    scale_factor: float


def _read_upload_bytes(upload: UploadFile, field_name: str) -> bytes:
    """Reads an uploaded file's raw bytes and enforces the size limit."""
    data = upload.file.read()
    if not data:
        raise FileProcessingError(f"'{field_name}' was uploaded but is empty.")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise FileProcessingError(
            f"'{field_name}' exceeds the size limit of {MAX_FILE_SIZE_BYTES / (1024*1024):.1f} MB."
        )
    return data


def detect_file_type(data: bytes) -> str:
    """Detects file format purely by examining magic bytes headers."""
    if data.startswith(b"\xFF\xD8\xFF"):
        return "jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1A\n"):
        return "png"
    else:
        raise FileProcessingError("Unsupported file format. Only JPEG and PNG images are supported.")


def create_working_image(img: Image.Image) -> Tuple[Image.Image, float]:
    """Creates a deterministic working image; downscales if needed, never upscales."""
    if img.mode != "RGB":
        img = img.convert("RGB")

    width, height = img.size
    ratio = 1.0

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT or (width * height) > MAX_PIXELS:
        width_ratio = MAX_IMAGE_WIDTH / width
        height_ratio = MAX_IMAGE_HEIGHT / height
        pixel_ratio = math.sqrt(MAX_PIXELS / (width * height))
        ratio = min(width_ratio, height_ratio, pixel_ratio, 1.0)

    if ratio < 1.0:
        new_width = max(1, int(width * ratio))
        new_height = max(1, int(height * ratio))
        working_img = img.resize((new_width, new_height), Image.Resampling.BICUBIC)
        return working_img, ratio

    return img.copy(), 1.0


def _build_page_from_image_bytes(data: bytes, page_source: Literal["front", "back"], page_index: int) -> NormalizedPage:
    file_type = detect_file_type(data)
    if file_type not in ("jpeg", "png"):
        raise FileProcessingError(f"Expected image for {page_source}, got {file_type}.")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except UnidentifiedImageError:
        raise FileProcessingError(f"Corrupted or unreadable image provided for {page_source}.")

    working_img, scale_factor = create_working_image(img)

    return NormalizedPage(
        original_image=img,
        working_image=working_img,
        page_source=page_source,
        page_index=page_index,
        original_width=img.width,
        original_height=img.height,
        working_width=working_img.width,
        working_height=working_img.height,
        scale_factor=scale_factor
    )


def process_uploaded_files(
    front: Optional[UploadFile],
    back: Optional[object] = None,
) -> List[NormalizedPage]:
    """
    Accepts direct image uploads: 'front' is required, 'back' is optional.
    If 'back' is None, empty, or unsupplied, it is safely ignored without error.
    """
    if front is None:
        raise FileProcessingError("Missing input: 'front' image is required.")

    pages = []
    front_data = _read_upload_bytes(front, "front")
    pages.append(_build_page_from_image_bytes(front_data, "front", 0))

    # Safely inspect back image without crashing if omitted or empty
    if back is not None and hasattr(back, "file") and getattr(back, "filename", None):
        try:
            back_data = back.file.read()
            if back_data and len(back_data) > 0:
                if len(back_data) > MAX_FILE_SIZE_BYTES:
                    raise FileProcessingError(
                        f"'back' exceeds the size limit of {MAX_FILE_SIZE_BYTES / (1024*1024):.1f} MB."
                    )
                pages.append(_build_page_from_image_bytes(back_data, "back", 1))
        except FileProcessingError:
            raise
        except Exception:
            pass

    return pages