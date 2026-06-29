from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import default_inputs_response
from app.export_utils import build_excel, build_pdf
from app.schemas import ExportRequest, SimulationRequest
from app.simulation import run_simulation

app = FastAPI(
    title="API Simulasi AC + HWST",
    description="Backend simulasi AC split + Hot Water Storage Tank berbasis web",
    version="1.0.0",
)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if FRONTEND_ORIGIN:
    ALLOWED_ORIGINS.append(FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Memudahkan preview Vercel seperti https://project-git-main-user.vercel.app
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "message": "Backend simulasi aktif"}


@app.get("/api/default-inputs")
def get_default_inputs() -> dict:
    return default_inputs_response()


@app.post("/api/run-simulation")
def post_run_simulation(payload: SimulationRequest) -> dict:
    try:
        return run_simulation(payload.config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-excel")
def post_export_excel(payload: ExportRequest) -> StreamingResponse:
    try:
        results = payload.results or run_simulation(payload.config)
        buffer = build_excel(results)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=laporan_simulasi_hwst.xlsx"},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-pdf")
def post_export_pdf(payload: ExportRequest) -> StreamingResponse:
    try:
        results = payload.results or run_simulation(payload.config)
        buffer = build_pdf(results)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=laporan_simulasi_hwst.pdf"},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
