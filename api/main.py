from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .body_limit import BodySizeLimit
from .deps import get_settings
from .routes import router

app = FastAPI(title="CruxCam API")

_settings = get_settings()
# Added first so CORS (added last) is outermost and 413 responses still carry CORS headers.
app.add_middleware(BodySizeLimit, max_bytes=_settings.max_upload_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_origin_regex=_settings.allowed_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)
