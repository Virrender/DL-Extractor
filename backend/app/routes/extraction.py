from fastapi import APIRouter, HTTPException

from app.schemas import ExtractionRequest
from app.services.image import decode_base64_image
from app.services.ocr import extract_text
from app.services.extractor import find_dob_candidate


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

    ocr_data = extract_text(image)

    dob = find_dob_candidate(ocr_data)

    return {
        "success": True,
        "data": {
            "date_of_birth": dob
        }
    }