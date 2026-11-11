from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import get_settings
from .routes import router

app = FastAPI(title="CruxCam API")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_origin_regex=_settings.allowed_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)
