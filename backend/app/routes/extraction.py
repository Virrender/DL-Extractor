from fastapi import APIRouter, HTTPException

from app.schemas import ExtractionRequest
from app.services.image import decode_base64_image
from app.services.ocr import extract_text
from app.services.extractor import extract_fields
from app.services.validator import validate_fields
from app.services.quality import check_image_quality


router = APIRouter()


@router.post("/extract")
async def extract(request: ExtractionRequest):
    try:
        image = decode_base64_image(request.image)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )



    quality = check_image_quality(image)

    if not quality["acceptable"]:
        return {
            "success": False,
            "reliable": False,
            "reupload_required": True,
            "message": "Image quality is insufficient for reliable extraction.",
            "quality": quality
        }

    
    ocr_data = extract_text(image)

    fields = extract_fields(ocr_data)
    
    validation_errors = validate_fields(fields)

    missing_fields = [
        field
        for field, value in fields.items()
        if value is None
    ]

    if missing_fields or validation_errors:
        return {
            "success": False,
            "reliable": False,
            "reupload_required": True,
            "message": (
            "Unable to reliably extract "
            "the required DL information."
        ),
            "missing_fields": missing_fields,
            "validation_errors": validation_errors
        }

    return {
        "success": True,
        "reliable": True,
        "reupload_required": False,
        "data": fields
    }