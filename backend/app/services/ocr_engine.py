"""
Core OCR Engine Layer.

Responsibilities:
- Initialize the PaddleOCR model safely as a global Singleton, using PaddleOCR's
  default detection/recognition parameters -- proven correct on real test
  cards -- plus the built-in document-orientation classifier (lossless
  0/90/180/270 rotation, safe to always run) with perspective-unwarping OFF
  (it visibly distorted already-flat images in testing).
- process_page(): runs OCR and returns BOTH the extracted OCRBlocks and the
  corrected (rotated) image PaddleOCR produced internally, so downstream
  steps (like photo extraction and QR detection) can reuse it.
- Handles residual arbitrary-angle skew (real tilts beyond clean 90-degree
  multiples) with one extra OCR pass, only when clearly needed (> 4 degrees).
- Polygon-geometry-based angle estimation: PaddleOCR v3's predict() API does
  not expose per-block rotation angles directly; we derive them from the
  quadrilateral polygon returned for each block.

NOTE on resampling: PIL's Image.rotate() only supports NEAREST, BILINEAR, or
BICUBIC -- LANCZOS is NOT valid here (it's resize()-only) and will raise a
ValueError. BICUBIC is the best of the three actually supported.
"""

import logging
import math
import statistics
import threading
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

from app.schemas import OCRBlock
from app.services.file_handler import NormalizedPage

logger = logging.getLogger(__name__)
logging.getLogger("ppocr").setLevel(logging.WARNING)

# Minimum number of text-line angle samples required before we trust the
# median estimate enough to attempt a fine-skew correction pass.
MIN_LINES_FOR_ANGLE_ESTIMATE = 3

# Only trigger a fine-skew correction when the estimated tilt exceeds this
# threshold (in degrees). Raised from 1.5 -> 4.0 after a real photo (near-
# perfectly aligned, but with natural noise in the angle estimate) falsely
# triggered a rotation that blurred bold text enough to break name reads.
# The built-in orientation classifier already handles the coarse 90-degree
# cases; this fires only for genuine moderate/severe tilts.
FINE_SKEW_THRESHOLD_DEGREES = 4.0

# Perspective/dewarping is a heavier model than the orientation classifier,
# AND it visibly damaged an already-flat test image. Keep this off by default.
ENABLE_DOC_UNWARPING = False


class OCREngineError(Exception):
    """Custom exception for OCR initialization or execution failures."""
    pass


class PaddleOCREngine:
    """
    Singleton wrapper for PaddleOCR — the heavy model is loaded exactly once.
    A class-level lock serializes inference calls because PaddleOCR's
    underlying inference session is not thread-safe for concurrent calls.
    (FastAPI's sync endpoints run in a thread pool.)
    """
    _instance = None
    _initialized = False
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PaddleOCREngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if PaddleOCR is None:
            raise OCREngineError("PaddleOCR package is not installed.")

        try:
            logger.info("Initializing PaddleOCR (CPU mode)...")
            self.ocr = PaddleOCR(
                lang="en",
                use_textline_orientation=True,
                use_doc_orientation_classify=True,   # lossless 0/90/180/270 correction
                use_doc_unwarping=ENABLE_DOC_UNWARPING,
                det_db_unclip_ratio=2.0,
            )
            PaddleOCREngine._initialized = True
            logger.info("PaddleOCR initialized successfully.")
        except Exception as e:
            import traceback
            PaddleOCREngine._initialized = False
            PaddleOCREngine._instance = None
            logger.error(f"PaddleOCR init failed:\n{traceback.format_exc()}")
            raise OCREngineError(f"Failed to initialize PaddleOCR: {e}")

    @classmethod
    def _reset_for_testing(cls):
        cls._instance = None
        cls._initialized = False

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _predict(self, img: Image.Image) -> Tuple[Optional[object], Image.Image]:
        """
        Runs a single PaddleOCR prediction pass.
        Returns (page_data, corrected_pil_image).
        corrected_pil_image is the image after PaddleOCR's internal lossless
        orientation correction; falls back to the original if unavailable.
        """
        img_array = np.array(img.convert("RGB"))
        img_array = img_array[:, :, ::-1]  # RGB → BGR for PaddleOCR

        with PaddleOCREngine._lock:
            raw_results = list(self.ocr.predict(img_array))

        if not raw_results:
            return None, img

        page_data = raw_results[0]
        corrected_img = img

        # Extract the orientation-corrected image PaddleOCR produced internally.
        # If doc_orientation_classify ran, the corrected image lives in
        # doc_preprocessor_res["output_img"] as a BGR ndarray.
        try:
            prep = (
                page_data.get("doc_preprocessor_res")
                if hasattr(page_data, "get")
                else None
            )
            if prep is not None:
                out_arr = prep.get("output_img") if hasattr(prep, "get") else None
                if out_arr is not None:
                    out_arr = np.asarray(out_arr)
                    if out_arr.ndim == 3 and out_arr.shape[2] == 3:
                        out_arr = out_arr[:, :, ::-1]  # BGR → RGB
                    corrected_img = Image.fromarray(out_arr.astype(np.uint8))
        except Exception as e:
            logger.warning(f"Could not extract corrected image from PaddleOCR result: {e}")

        return page_data, corrected_img

    @staticmethod
    def _parse_blocks(
        page_data: object,
        page_source: str,
        page_index: int,
        source_width: int,
        source_height: int,
    ) -> List[OCRBlock]:
        """
        Converts PaddleOCR v3 predict() output into a list of OCRBlock objects.

        PaddleOCR v3 predict() returns a list of result dicts. Each dict has
        a key 'rec_texts' (list of str), 'rec_scores' (list of float), and
        'det_polys' or 'dt_polys' (list of Nx2 arrays — typically N=4 for a
        quadrilateral bounding box).
        """
        blocks: List[OCRBlock] = []
        if page_data is None:
            return blocks

        # Support both dict-style and object-style results from different
        # PaddleOCR v3 sub-versions.
        def _get(obj, *keys):
            for k in keys:
                try:
                    v = obj[k] if hasattr(obj, '__getitem__') else getattr(obj, k, None)
                    if v is not None:
                        return v
                except (KeyError, TypeError):
                    pass
            return None

        texts = _get(page_data, "rec_texts", "rec_text") or []
        scores = _get(page_data, "rec_scores", "rec_score") or []
        # PaddleOCR v3 uses 'det_polys'; older builds used 'dt_polys'
        polys = _get(page_data, "det_polys", "dt_polys") or []

        for text, score, poly in zip(texts, scores, polys):
            text = text.strip()
            if not text:
                continue

            try:
                pts = np.array(poly, dtype=np.float32).reshape(-1, 2)
                if len(pts) < 4:
                    continue

                # Use first 4 points as the canonical quadrilateral.
                quad = pts[:4]
                polygon = [(float(p[0]), float(p[1])) for p in quad]

                xs = [p[0] for p in polygon]
                ys = [p[1] for p in polygon]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                cx = (x_min + x_max) / 2.0
                cy = (y_min + y_max) / 2.0

                blocks.append(OCRBlock(
                    text=text,
                    ocr_confidence=float(score),
                    polygon=polygon,
                    rect=(x_min, y_min, x_max, y_max),
                    center=(cx, cy),
                    page_source=page_source,
                    page_index=page_index,
                    source_width=source_width,
                    source_height=source_height,
                ))
            except Exception as e:
                logger.debug(f"Skipping malformed block: {e}")
                continue

        return blocks

    @staticmethod
    def _estimate_skew_from_blocks(blocks: List[OCRBlock]) -> Optional[float]:
        """
        Estimates the document's fine-skew angle (in degrees) from OCRBlock
        polygon geometry.

        Each text-line polygon is a quadrilateral. The dominant (longer)
        bottom edge of the quad gives the text-line's orientation angle. We
        take the median across all blocks with high confidence to get a robust
        estimate.

        Returns the angle in degrees (positive = counter-clockwise tilt),
        or None if there are too few samples to be reliable.
        """
        angles: List[float] = []

        for block in blocks:
            if block.ocr_confidence < 0.6:
                continue
            if len(block.polygon) < 4:
                continue

            pts = block.polygon
            # For a standard text-line quad the bottom edge is pts[2]→pts[3]
            # (PaddleOCR orders: top-left, top-right, bottom-right, bottom-left).
            # We use the longer of the two horizontal edges for robustness.
            def _edge_angle(p1, p2):
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                if abs(dx) < 1e-6:
                    return None
                return math.degrees(math.atan2(dy, dx))

            top_angle = _edge_angle(pts[0], pts[1])
            bot_angle = _edge_angle(pts[3], pts[2])

            # Pick the edge whose horizontal span is larger (more reliable).
            top_span = abs(pts[1][0] - pts[0][0])
            bot_span = abs(pts[2][0] - pts[3][0])

            angle = bot_angle if bot_span >= top_span else top_angle
            if angle is None:
                continue

            # Normalise to (-45, 45) range — beyond that it's a gross
            # orientation error that the coarse classifier should have caught.
            if angle > 45:
                angle -= 90
            elif angle < -45:
                angle += 90

            angles.append(angle)

        if len(angles) < MIN_LINES_FOR_ANGLE_ESTIMATE:
            return None

        return statistics.median(angles)

    @staticmethod
    def _count_long_words(blocks: List[OCRBlock]) -> int:
        """Proxy for OCR quality: count blocks with text of 4+ chars."""
        return sum(1 for b in blocks if len(b.text) >= 4)

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------
    def process_page(
        self,
        page: NormalizedPage,
    ) -> Tuple[List[OCRBlock], Image.Image]:
        """
        Full OCR pipeline for one page image. Runs on page.working_image
        (the bounded/downscaled image) -- never page.original_image directly --
        to keep inference memory/time bounded on constrained hardware.

        page_source / page_index / dimensions are read directly off the
        NormalizedPage object, not passed in separately.
        """
        img = page.working_image
        w, h = img.size

        # ── Step 1: initial OCR pass ──────────────────────────────────────────
        page_data, corrected_img = self._predict(img)
        cw, ch = corrected_img.size
        blocks = self._parse_blocks(page_data, page.page_source, page.page_index, cw, ch)

        if not blocks:
            logger.warning(f"No OCR blocks returned for page {page.page_source}.")
            return [], corrected_img

        # ── Step 2: estimate fine-skew ─────────────────────────────────────────
        skew = self._estimate_skew_from_blocks(blocks)
        if skew is None or abs(skew) < FINE_SKEW_THRESHOLD_DEGREES:
            return blocks, corrected_img

        logger.info(
            f"Estimated fine skew {skew:.2f}° on page '{page.page_source}' — "
            f"attempting correction pass."
        )

        # ── Step 3: fine-skew correction ──────────────────────────────────────
        baseline_quality = self._count_long_words(blocks)
        best_blocks = blocks
        best_img = corrected_img
        best_quality = baseline_quality

        for sign in (-1, +1):
            angle_to_apply = sign * skew
            rotated = corrected_img.rotate(
                angle_to_apply,
                resample=Image.BICUBIC,
                expand=True,
                fillcolor=(255, 255, 255),
            )
            rot_w, rot_h = rotated.size
            pd2, _ = self._predict(rotated)
            new_blocks = self._parse_blocks(
                pd2, page.page_source, page.page_index, rot_w, rot_h
            )
            quality = self._count_long_words(new_blocks)
            if quality > best_quality:
                best_quality = quality
                best_blocks = new_blocks
                best_img = rotated

        return best_blocks, best_img
