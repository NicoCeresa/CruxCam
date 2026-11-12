#!/bin/sh
# --no-proxy-headers: uvicorn must not rewrite the client address from X-Forwarded-For
# (in trust-all mode it takes the client-supplied leftmost entry). The app decides that
# itself via CRUXCAM_PROXY_HOPS — see _client_ip in api/routes.py.
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers
