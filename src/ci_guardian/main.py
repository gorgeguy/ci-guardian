"""FastAPI application entry point."""

import argparse
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ci_guardian.config import get_settings
from ci_guardian.webhook import router as webhook_router

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    """Configure structured logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("CI Guardian starting up")
    yield
    logger.info("CI Guardian shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CI Guardian",
        description="Automated CI failure detection and remediation",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/metrics")
    async def metrics() -> JSONResponse:
        """Prometheus metrics endpoint (placeholder)."""
        # TODO: Implement actual metrics collection
        return JSONResponse(
            content={
                "failures_received": 0,
                "fixes_attempted": 0,
                "prs_created": 0,
            }
        )

    return app


app = create_app()


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="CI Guardian - Automated CI failure remediation")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the webhook server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    if args.command == "serve":
        settings = get_settings()
        setup_logging(settings.log_level)
        uvicorn.run(
            "ci_guardian.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
