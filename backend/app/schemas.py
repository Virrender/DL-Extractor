from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    image: str
    back_image: str | None = None