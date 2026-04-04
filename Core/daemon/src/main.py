"""
ScientificState Local Execution Daemon
FastAPI sidecar — localhost only boundary enforced.

Start with:
    uv run python src/main.py
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent to path so imports work when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.routes import diagnostics, discovery, domains, export, health, ingest, modules, monitoring, registry, replication, runs, workspaces
from src.routes.monitoring import MetricsMiddleware
from src.storage.schema import init_db

logger = logging.getLogger("scientificstate.daemon")

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    logger.info("ScientificState daemon starting up …")

    # Initialise SQLite schema (idempotent)
    await init_db()
    logger.info("SQLite schema ready.")

    # Discover and register domains via framework DomainRegistry
    try:
        from src.storage.domain_registry import build_registry

        registry = build_registry()
        loaded = registry.discover_and_register()  # sync — returns list[str]
        app.state.domain_registry = registry
        logger.info("Domain registry ready: %d domain(s) loaded: %s", len(loaded), loaded)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Domain discovery failed (continuing with 0 domains): %s", exc)
        from scientificstate.domain_registry.registry import DomainRegistry

        app.state.domain_registry = DomainRegistry()

    logger.info("Daemon ready — listening on localhost.")
    yield

    logger.info("Daemon shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ScientificState Daemon",
    description="Local scientific execution daemon — localhost boundary only.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Localhost-only CORS (Desktop WebView connects from file:// or localhost origin)
# Metrics middleware — counts requests and errors for /monitoring/metrics
app.add_middleware(MetricsMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "tauri://localhost",
        "http://localhost:1420",  # Tauri dev server default port
        "http://localhost:5173",  # Vite default
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Accept"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(domains.router)
app.include_router(ingest.router)
app.include_router(workspaces.router)
app.include_router(runs.router)
app.include_router(modules.router)
app.include_router(registry.router)
app.include_router(export.router)
app.include_router(replication.router)
app.include_router(discovery.router)
app.include_router(diagnostics.router)
app.include_router(monitoring.router)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def start() -> None:
    """Entry point for `uv run python src/main.py`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",  # LOCALHOST ONLY — never 0.0.0.0
        port=9473,  # Plan-mandated port (Execution_Plan_Phase0.md §4.1)
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    start()
