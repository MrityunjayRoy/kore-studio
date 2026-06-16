from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.pipeline.noise_reducer_service import NoiseReducer
from app.routers.ingestion import router as ingestion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    noise_reducer = NoiseReducer()
    app.state.noise_reducer = noise_reducer
    yield


app = FastAPI(title="Karaoke Mixing Pipeline", lifespan=lifespan)
app.include_router(ingestion_router)
