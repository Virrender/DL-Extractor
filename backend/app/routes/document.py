"""
Unified Document Extraction Endpoint.

Single entrypoint: upload front (+ optional back) images of ANY supported
ID document type. Pipeline:

  1. OCR runs once per page -- reused for classification, the OCR-based
     field extraction, and (implicitly) the corrected image for QR/photo.
  2. classify_document() decides driving_licence / aadhaar_card / unknown
     from keyword + pattern evidence.
  3. The same deterministic OCR-based extractor used by the standalone
     endpoints runs, producing a baseline result.
  4. QR detection runs on each CORRECTED (orientation-fixed) page image;
     where it decodes successfully, those fields OVERLAY the OCR result.
     After overlay, status and missing_fields are recomputed from scratch
     so a card that was "partial" after OCR can correctly become "success".
  5. Cardholder photo extraction runs on the corrected front image.

`extraction_source` tells callers exactly where fields came from:
  "qr", "ocr", "ocr+qr", or "none" (unknown document type).
"""

import base64
import logging
from typing import Optional, Union
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.schemas import (
    UnifiedExtractionResponse, DrivingLicenceResponse, AadhaarResponse,
    AadhaarFrontFields, AadhaarBackFields,
    DrivingLicenceFrontFields, DrivingLicenceBackFields,
    ExtractedField, QRPayloadRequest
)
from app.services.file_handler import process_uploaded_files, FileProcessingError
from app.services.ocr_engine import PaddleOCREngine, OCREngineError
from app.services.photo_extractor import extract_portrait_photo
from app.services.document_classifier import classify_document
from app.services.qr_extractor import extract_qr_data, parse_aadhaar_qr, parse_dl_qr
from app.services.common_extractors import parse_calendar_date
from app.services.extractors.dl_extractor import DrivingLicenceExtractor
from app.services.extractors.aadhaar_extractor import AadhaarExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["extraction"])

_dl_extractor = DrivingLicenceExtractor()
_aadhaar_extractor = AadhaarExtractor()


# =============================================================================
# Helpers
# =============================================================================

def _qr_field_to_extracted(value: str, source_page: str) -> ExtractedField:
    """
    Wrap a QR-decoded string value in an ExtractedField.
    QR fields are structural decodes (not probabilistic OCR reads), so
    confidence is always 1.0 and both anchor_matched and format_valid are True.
    """
    return ExtractedField(
        value=value,
        ocr_confidence=1.0,
        anchor_matched=True,
        format_valid=True,
        composite_score=1.0,
        raw_text=value,
        bounding_box=None,
        source_page=source_page,
    )


def _recompute_aadhaar_status(result: AadhaarResponse) -> None:
    """
    Recompute missing_fields and status on an AadhaarResponse in-place.
    Called after any QR overlay so status accurately reflects the final
    merged field set (a partial result can become success after QR fills gaps).
    """
    missing = []
    if not (result.front and result.front.aadhaar_number):
        missing.append("aadhaar_number")
    if not (result.front and result.front.name):
        missing.append("name")
    if not (result.front and result.front.dob):
        missing.append("dob")

    result.missing_fields = missing

    if len(missing) == 0:
        result.status = "success"
    elif len(missing) == 3:
        result.status = "failed"
    else:
        result.status = "partial"


def _recompute_dl_status(result: DrivingLicenceResponse) -> None:
    """
    Recompute missing_fields and status on a DrivingLicenceResponse in-place.
    Called after any QR overlay.
    """
    missing = []
    if not (result.front and result.front.id_number):
        missing.append("id_number")
    if not (result.front and result.front.name):
        missing.append("name")
    if not (result.front and result.front.dob):
        missing.append("dob")

    result.missing_fields = missing

    if len(missing) == 0:
        result.status = "success"
    elif len(missing) == 3:
        result.status = "failed"
    else:
        result.status = "partial"


def _merge_qr_into_aadhaar(
    ocr_result: AadhaarResponse, qr_fields: dict
) -> str:
    """
    Overlay QR-decoded fields onto an OCR-based AadhaarResponse.
    QR fields are preferred because they are structural decodes, not
    probabilistic reads. Note: Aadhaar Secure QR structurally cannot supply
    the full 12-digit Aadhaar number — that always comes from OCR.

    Returns "qr" if ALL of the three mandatory fields now come from QR,
    "ocr+qr" if both sources contributed, or "ocr" if QR added nothing new.
    """
    used_qr = False

    if qr_fields.get("aadhaar_number") and not ocr_result.front.aadhaar_number:
        ocr_result.front.aadhaar_number = _qr_field_to_extracted(
            qr_fields["aadhaar_number"].strip(), "front"
        )
        used_qr = True
    elif qr_fields.get("reference_id") and not ocr_result.front.aadhaar_number:
        ref = str(qr_fields["reference_id"]).strip()
        last4 = ref[:4] if len(ref) >= 4 and ref[:4].isdigit() else None
        if last4:
            ocr_result.front.aadhaar_number = _qr_field_to_extracted(f"XXXX XXXX {last4}", "front")
            used_qr = True

    if qr_fields.get("_photo_b64"):
        ocr_result.photo_base64 = qr_fields["_photo_b64"]

    if qr_fields.get("name"):
        ocr_result.front.name = _qr_field_to_extracted(
            qr_fields["name"].strip().upper(), "front"
        )
        used_qr = True

    if qr_fields.get("dob"):
        raw_dob = qr_fields["dob"].strip()
        if len(raw_dob) == 4 and raw_dob.isdigit():
            ok, norm = True, f"{raw_dob}-01-01"
        else:
            ok, norm = parse_calendar_date(raw_dob)
        if ok:
            ocr_result.front.dob = _qr_field_to_extracted(norm, "front")
            used_qr = True

    if qr_fields.get("gender"):
        g = qr_fields["gender"].strip().upper()
        if g in ("M", "MALE"):
            g = "MALE"
        elif g in ("F", "FEMALE"):
            g = "FEMALE"
        elif g in ("T", "TRANSGENDER"):
            g = "TRANSGENDER"
        ocr_result.front.gender = _qr_field_to_extracted(g, "front")
        used_qr = True

    # Address fields from QR (if present)
    addr_parts = []
    for key in ("house", "street", "location", "landmark", "vtc",
                "sub_district", "district", "state", "pincode"):
        val = qr_fields.get(key, "").strip()
        if val:
            addr_parts.append(val)

    if addr_parts:
        full_address = ", ".join(addr_parts)
        if ocr_result.back is None:
            from app.schemas import AadhaarBackFields
            ocr_result.back = AadhaarBackFields()
        ocr_result.back.address = _qr_field_to_extracted(full_address, "back")
        if qr_fields.get("pincode"):
            ocr_result.back.pin_code = _qr_field_to_extracted(
                qr_fields["pincode"].strip(), "back"
            )
        used_qr = True

    # ── Recompute status after merge ──────────────────────────────────────────
    _recompute_aadhaar_status(ocr_result)

    return "ocr+qr" if used_qr else "ocr"


def _merge_qr_into_dl(
    ocr_result: DrivingLicenceResponse, qr_fields: dict
) -> str:
    """
    Overlay QR-decoded fields onto an OCR-based DrivingLicenceResponse.
    Returns "ocr+qr" if QR contributed, "ocr" otherwise.
    """
    used_qr = False

    dl_val = qr_fields.get("id_number") or qr_fields.get("dl_number")
    if dl_val and not ocr_result.front.id_number:
        ocr_result.front.id_number = _qr_field_to_extracted(
            str(dl_val).strip(), "front"
        )
        used_qr = True

    if qr_fields.get("dob"):
        ok, norm = parse_calendar_date(qr_fields["dob"])
        if ok and not ocr_result.front.dob:
            ocr_result.front.dob = _qr_field_to_extracted(norm, "front")
            used_qr = True

    if qr_fields.get("name") and not ocr_result.front.name:
        ocr_result.front.name = _qr_field_to_extracted(
            qr_fields["name"].strip().upper(), "front"
        )
        used_qr = True

    if qr_fields.get("issue_date"):
        ok, norm = parse_calendar_date(qr_fields["issue_date"])
        if ok and not ocr_result.front.issue_date:
            ocr_result.front.issue_date = _qr_field_to_extracted(norm, "front")
            used_qr = True

    if qr_fields.get("expiry_date"):
        ok, norm = parse_calendar_date(qr_fields["expiry_date"])
        if ok and not ocr_result.front.expiry_date:
            ocr_result.front.expiry_date = _qr_field_to_extracted(norm, "front")
            used_qr = True

    # ── Recompute status after merge ──────────────────────────────────────────
    _recompute_dl_status(ocr_result)

    return "ocr+qr" if used_qr else "ocr"


# =============================================================================
# Route
# =============================================================================

@router.post("/extract", response_model=UnifiedExtractionResponse)
async def extract_document(
    front_image: UploadFile = File(..., description="Front side of the ID document (required)"),
    back_image: Union[UploadFile, str, None] = File(
        default=None,
        description="Back side of the ID document (optional)"
    ),
):
    """
    Unified document extraction endpoint.
    Accepts front (required) and back (optional) images of an Aadhaar card
    or Driving Licence and returns structured field data + passport photo.
    """
    # ── 1. Validate & normalize uploaded images ───────────────────────────────
    # Safely treat non-file or empty back uploads as None
    actual_back = back_image if (isinstance(back_image, StarletteUploadFile) and getattr(back_image, "filename", None)) else None
    try:
        pages = process_uploaded_files(front_image, actual_back)
    except FileProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # ── 2. OCR each page once; keep both blocks and corrected images ──────────
    try:
        engine = PaddleOCREngine()
    except OCREngineError as e:
        raise HTTPException(status_code=503, detail=f"OCR engine unavailable: {e}")

    all_blocks = []
    corrected_images: dict = {}   # page_source → PIL Image
    pages_processed = []

    for page in pages:
        try:
            blocks, corrected_img = engine.process_page(page)
            all_blocks.extend(blocks)
            corrected_images[page.page_source] = corrected_img
            pages_processed.append(page.page_source)
        except Exception as e:
            logger.error(f"OCR failed for page '{page.page_source}': {e}")

    if not all_blocks:
        return UnifiedExtractionResponse(
            document_type="unknown",
            classification_confidence=0.0,
            extraction_source="none",
            result=None,
            photo_base64=None,
            warnings=["OCR returned no text blocks for any uploaded page."],
        )

    # ── 3. Classify document type ─────────────────────────────────────────────
    doc_type, confidence = classify_document(all_blocks)

    if doc_type == "unknown":
        return UnifiedExtractionResponse(
            document_type="unknown",
            classification_confidence=confidence,
            extraction_source="none",
            result=None,
            photo_base64=None,
            warnings=[
                "Could not confidently identify document type. "
                "Please ensure the image is clear and contains a supported ID document."
            ],
        )

    # ── 4. OCR-based field extraction ─────────────────────────────────────────
    if doc_type == "driving_licence":
        ocr_result: DrivingLicenceResponse = _dl_extractor.extract(
            all_blocks, pages_processed=pages_processed
        )
    else:  # aadhaar_card
        ocr_result: AadhaarResponse = _aadhaar_extractor.extract(
            all_blocks, pages_processed=pages_processed
        )

    # ── 5. QR extraction on corrected images (overlay onto OCR) ──────────────
    extraction_source = "ocr"
    front_corrected = corrected_images.get("front")
    back_corrected = corrected_images.get("back")

    for src_label, corrected_img in [("front", front_corrected), ("back", back_corrected)]:
        if corrected_img is None:
            continue
        try:
            qr_fields = extract_qr_data(corrected_img, doc_type)
        except Exception as e:
            logger.warning(f"QR extraction failed for {src_label}: {e}")
            continue

        if not qr_fields:
            continue

        if doc_type == "aadhaar_card":
            extraction_source = _merge_qr_into_aadhaar(ocr_result, qr_fields)
        else:
            extraction_source = _merge_qr_into_dl(ocr_result, qr_fields)

    # ── 6. Photo extraction from orientation-corrected front image ────────────
    photo_b64: Optional[str] = None
    if front_corrected is not None:
        try:
            photo_bytes = extract_portrait_photo(front_corrected)
            if photo_bytes:
                photo_b64 = base64.b64encode(photo_bytes).decode("ascii")
        except Exception as e:
            logger.warning(f"Photo extraction failed: {e}")
            ocr_result.warnings = list(ocr_result.warnings) + [
                f"Photo extraction encountered an error: {e}"
            ]

    # photo_base64 lives on BOTH the inner result and the outer envelope
    ocr_result.photo_base64 = photo_b64

    # ── 7. Assemble unified response ──────────────────────────────────────────
    return UnifiedExtractionResponse(
        document_type=doc_type,
        classification_confidence=confidence,
        extraction_source=extraction_source,
        result=ocr_result,
        photo_base64=photo_b64,
        warnings=ocr_result.warnings,
    )


@router.post("/extract/qr-payload", response_model=UnifiedExtractionResponse)
async def extract_from_qr_payload(payload: QRPayloadRequest):
    """
    QR-only fast path: takes a raw decoded QR string (already scanned
    client-side by the live camera UI) and returns structured fields with
    NO image upload and NO OCR involved -- pure structural parsing, so this
    responds in milliseconds.
    """
    raw = payload.raw_payload
    hint = payload.document_type

    logger.info(
        f"QR payload received: len={len(raw)}, preview={raw[:60]!r}, isdigit={raw.strip().isdigit()}"
    )

    doc_type: Optional[str] = None
    qr_fields: Optional[dict] = None

    # Try Aadhaar first unless explicitly told it's a DL.
    # Supports both new Secure QR and standard XML QR formats.
    if hint != "driving_licence":
        qr_fields = parse_aadhaar_qr(raw)
        if qr_fields:
            doc_type = "aadhaar_card"

    if qr_fields is None and hint != "aadhaar_card":
        qr_fields = parse_dl_qr(raw)
        if qr_fields:
            doc_type = "driving_licence"

    if not qr_fields or not doc_type:
        logger.warning(f"Could not parse QR payload (len={len(raw)}).")
        raise HTTPException(
            status_code=422,
            detail="Could not parse this QR payload as either an Aadhaar Secure QR or a Driving Licence QR."
        )

    # A bare verification URL (DL QR with no other data) has nothing to overlay.
    if qr_fields.get("_url_only"):
        raise HTTPException(
            status_code=422,
            detail="QR contained only a verification URL with no embedded field data."
        )

    photo_b64: Optional[str] = None
    if doc_type == "aadhaar_card":
        ocr_result = AadhaarResponse(status="failed", front=AadhaarFrontFields())
        extraction_source = _merge_qr_into_aadhaar(ocr_result, qr_fields)
        photo_b64 = qr_fields.get("_photo_b64") or ocr_result.photo_base64
    else:
        ocr_result = DrivingLicenceResponse(status="failed", front=DrivingLicenceFrontFields())
        extraction_source = _merge_qr_into_dl(ocr_result, qr_fields)
        photo_b64 = None

    return UnifiedExtractionResponse(
        document_type=doc_type,
        classification_confidence=1.0,   # QR structurally confirms document type
        extraction_source=extraction_source,
        result=ocr_result,
        photo_base64=photo_b64,
        warnings=ocr_result.warnings,
    )