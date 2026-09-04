from fastapi import APIRouter, HTTPException

from app.schemas import ExtractionRequest
from app.services.image import decode_base64_image
from app.services.quality import check_image_quality
from app.services.ocr import extract_text
from app.services.extractor import extract_fields
from app.services.address import extract_address
from app.services.validator import validate_fields


router = APIRouter()


@router.post("/extract")
async def extract(request: ExtractionRequest):

    # --------------------------------------------------
    # FRONT SIDE
    # --------------------------------------------------

    try:
        image = decode_base64_image(
            request.image
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    front_quality = check_image_quality(
        image
    )

    if not front_quality["acceptable"]:
        return {
            "success": False,
            "reliable": False,
            "reupload_required": True,
            "message": (
                "Front-side image quality is "
                "insufficient for reliable extraction."
            ),
            "quality": {
                "front": front_quality
            }
        }

    # --------------------------------------------------
    # FRONT OCR
    # --------------------------------------------------

    ocr_data = extract_text(image)

    # --------------------------------------------------
    # FRONT EXTRACTION
    # --------------------------------------------------

    fields = extract_fields(
        ocr_data
    )

    validation_errors = validate_fields(
        fields
    )

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

    # --------------------------------------------------
    # OPTIONAL BACK SIDE
    # --------------------------------------------------

    address = None
    back_quality = None
    back_side_status = "not_provided"

    if request.back_image:

        try:
            back_image = decode_base64_image(
                request.back_image
            )

        except ValueError:
            back_side_status = "invalid_image"

        else:

            back_quality = check_image_quality(
                back_image
            )

            if not back_quality["acceptable"]:

                back_side_status = "poor_quality"

            else:

                back_ocr_data = extract_text(
                    back_image
                )

                address = extract_address(
                    back_ocr_data
                )

                if address is not None:
                    back_side_status = "processed"
                else:
                    back_side_status = "address_not_found"

    # --------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------

    response = {
        "success": True,
        "reliable": True,
        "reupload_required": False,
        "data": fields
    }

    if request.back_image:
        response["back_side"] = {
            "status": back_side_status,
            "address": address
        }

        if back_quality is not None:
            response["back_side"]["quality"] = (
                back_quality
            )

    return response