"""
Data contracts and schemas for the Document Intelligence pipeline.

Requests are now handled as direct multipart file uploads 
"""

from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# Generic OCR & Extraction Models (Engine-Agnostic)
# ============================================================================

class OCRBlock(BaseModel):
    """Standardized internal representation of a detected OCR text block."""
    text: str = Field(..., description="Recognized text string")
    ocr_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Raw confidence score from OCR engine (0.0 to 1.0)"
    )
    polygon: list[tuple[float, float]] = Field(
        ..., min_length=4, description="Four corner coordinates [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]"
    )
    rect: tuple[float, float, float, float] = Field(
        ..., description="Axis-aligned bounding box (x_min, y_min, x_max, y_max)"
    )
    center: tuple[float, float] = Field(
        ..., description="Center point coordinates (cx, cy) for tilt-tolerant spatial matching"
    )
    page_source: Literal["front", "back"] = Field(
        ..., description="Origin side/page of the document image"
    )
    page_index: int = Field(
        ..., ge=0, description="Zero-based index of the page within the source document"
    )
    source_width: int = Field(
        ..., gt=0, description="Width in pixels of the working image passed to OCR"
    )
    source_height: int = Field(
        ..., gt=0, description="Height in pixels of the working image passed to OCR"
    )


class ExtractedField(BaseModel):
    """Field-level extraction result with multi-signal confidence and provenance tracing."""
    value: str = Field(..., description="Normalized, cleaned field value")
    ocr_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Raw OCR character recognition confidence"
    )
    anchor_matched: bool = Field(
        ..., description="True if the field was identified via an anchor label/keyword"
    )
    format_valid: bool = Field(
        ..., description="True if the extracted value passed regex or checksum format rules"
    )
    composite_score: float = Field(
        ..., ge=0.0, le=1.0, description="Synthesized field-level confidence score (0.0 to 1.0)"
    )
    raw_text: Optional[str] = Field(
        default=None, description="Original unnormalized OCR text before regex cleaning"
    )
    bounding_box: Optional[tuple[float, float, float, float]] = Field(
        default=None, description="Bounding box (x_min, y_min, x_max, y_max) of the extracted text"
    )
    source_page: Optional[Literal["front", "back"]] = Field(
        default=None, description="Document page/side from which this field originated"
    )


# ============================================================================
# Driving Licence Response Models
# ============================================================================

class DrivingLicenceFrontFields(BaseModel):
    id_number: Optional[ExtractedField] = Field(default=None, description="Driving Licence number (mandatory)")
    name: Optional[ExtractedField] = Field(default=None, description="Cardholder full name (mandatory)")
    dob: Optional[ExtractedField] = Field(default=None, description="Date of birth (mandatory)")
    father_or_husband_name: Optional[ExtractedField] = Field(default=None, description="Father/Husband/Guardian name")
    blood_group: Optional[ExtractedField] = Field(default=None, description="Blood group if present")
    issue_date: Optional[ExtractedField] = Field(default=None, description="Licence issue date")
    expiry_date: Optional[ExtractedField] = Field(default=None, description="Licence expiry date")


class DrivingLicenceBackFields(BaseModel):
    address: Optional[ExtractedField] = Field(default=None, description="Full residential address")
    pin_code: Optional[ExtractedField] = Field(default=None, description="6-digit postal PIN code")


class DrivingLicenceResponse(BaseModel):
    document_type: Literal["driving_licence"] = "driving_licence"
    status: Literal["success", "partial", "failed"] = Field(
        ..., description="'success' (all mandatory fields present), 'partial', or 'failed'"
    )
    front: DrivingLicenceFrontFields = Field(default_factory=DrivingLicenceFrontFields)
    back: Optional[DrivingLicenceBackFields] = Field(default=None)
    missing_fields: list[str] = Field(default_factory=list)
    pages_processed: list[Literal["front", "back"]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    photo_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded JPEG (~10-30KB) of the cardholder's photo, or null if not confidently detected"
    )


# ============================================================================
# Aadhaar Card Response Models
# ============================================================================

class AadhaarFrontFields(BaseModel):
    aadhaar_number: Optional[ExtractedField] = Field(default=None, description="12-digit Aadhaar number (mandatory)")
    name: Optional[ExtractedField] = Field(default=None, description="Cardholder full name (mandatory)")
    dob: Optional[ExtractedField] = Field(default=None, description="Date of birth (mandatory)")
    gender: Optional[ExtractedField] = Field(default=None, description="Gender if present")


class AadhaarBackFields(BaseModel):
    address: Optional[ExtractedField] = Field(default=None, description="Full residential address")
    pin_code: Optional[ExtractedField] = Field(default=None, description="6-digit postal PIN code")


class AadhaarResponse(BaseModel):
    document_type: Literal["aadhaar_card"] = "aadhaar_card"
    status: Literal["success", "partial", "failed"] = Field(
        ..., description="'success' (all mandatory fields present), 'partial', or 'failed'"
    )
    front: AadhaarFrontFields = Field(default_factory=AadhaarFrontFields)
    back: Optional[AadhaarBackFields] = Field(default=None)
    missing_fields: list[str] = Field(default_factory=list)
    pages_processed: list[Literal["front", "back"]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    photo_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded JPEG (~10-30KB) of the cardholder's photo, or null if not confidently detected"
    )


# ============================================================================
# Unified Auto-Detection Response Model
# ============================================================================

class UnifiedExtractionResponse(BaseModel):
    document_type: Literal["driving_licence", "aadhaar_card", "unknown"] = Field(
        ..., description="Auto-detected document type"
    )
    classification_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Rough evidence-strength score for the classification -- NOT a calibrated probability"
    )
    extraction_source: Literal["qr", "ocr", "ocr+qr", "none"] = Field(
        ...,
        description=(
            "Where the returned fields came from: a QR code decode, OCR text "
            "extraction, a merge of both (QR fields overlaid onto an OCR "
            "baseline), or 'none' if document_type is 'unknown'"
        )
    )
    result: Optional[Union[DrivingLicenceResponse, AadhaarResponse]] = Field(
        default=None,
        description="Extracted document fields, shaped per document_type; null if document_type is 'unknown'"
    )
    photo_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded JPEG (~10-30KB) of the cardholder's photo, or null if not confidently detected"
    )
    warnings: list[str] = Field(default_factory=list)

class QRPayloadRequest(BaseModel):
    """Request body for the QR-only fast-path endpoint (no image upload)."""
    raw_payload: str = Field(..., min_length=1, description="Raw decoded QR text, exactly as read off the device camera")
    document_type: Optional[Literal["aadhaar_card", "driving_licence"]] = Field(
        default=None,
        description="Optional hint. If omitted, the backend attempts Aadhaar Secure QR parsing first, then DL parsing."
    )
