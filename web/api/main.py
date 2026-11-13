"""Development API. It listens on this computer only."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.errors import LedgerError, RoleError
from web.api.auth_stub import BIND_HOST, assert_development
from web.api.routes import router


def create_app() -> FastAPI:
    assert_development()
    app = FastAPI(title="VC Accountant", version="0.5.0")
    app.include_router(router)

    @app.exception_handler(RoleError)
    def _role(_request, exc: RoleError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(LedgerError)
    def _ledger(_request, exc: LedgerError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


def serve() -> None:
    global app
    assert_development()
    if app is None:
        app = create_app()
    import uvicorn

    uvicorn.run(app, host=BIND_HOST, port=int(os.environ.get("VCA_PORT", "8000")))


app = None
if os.environ.get("VCA_ENV") == "development":
    app = create_app()
