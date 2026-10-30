from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from logic import calculate_recommendation

app = FastAPI(title="АгроСенс")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgroInput(BaseModel):
    lat: float
    lon: float
    ph: float
    soil_type: str
    crop: str = "discover"
    mode: str = "check"

@app.post("/api/recommend")
def recommend(data: AgroInput):
    return calculate_recommendation(data.model_dump())

app.mount("/", StaticFiles(directory=".", html=True), name="site")