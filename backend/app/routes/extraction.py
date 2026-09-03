from fastapi import APIRouter, HTTPException

from app.schemas import ExtractionRequest
from app.services.image import decode_base64_image

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

    height, width = image.shape[:2]

    return {
        "message": "Image received successfully",
        "width": width,
        "height": height
    }