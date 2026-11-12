"""Request body size limit, enforced while the body is received.

FastAPI parses multipart uploads (spooling them to disk) before the endpoint runs, so a
size check inside an endpoint happens only after the whole upload is on disk. This ASGI
middleware rejects oversized bodies up front (declared Content-Length) or as soon as the
streamed bytes pass the limit (uploads without a Content-Length).
"""
import json

from fastapi import HTTPException


class BodySizeLimit:

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)   # body never read
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # HTTPException passes through FastAPI's body parsing unchanged → 413.
                    raise HTTPException(status_code=413, detail=self._detail())
            return message

        await self.app(scope, limited_receive, send)

    def _detail(self) -> str:
        return f"File too large (max {self.max_bytes // (1024 * 1024)} MB)"

    async def _reject(self, send) -> None:
        body = json.dumps({"detail": self._detail()}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
