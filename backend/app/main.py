from fastapi import FastAPI

from app.routes.extraction import router as extraction_router


app = FastAPI(
    title="HP Driving Licence Extractor"
)


app.include_router(extraction_router)


@app.get("/")
async def root():
    return {
        "message": "DL extractor is running"
    }