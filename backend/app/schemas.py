from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    image: str