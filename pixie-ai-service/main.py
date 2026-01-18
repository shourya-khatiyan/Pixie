"""Pixie AI Service - FastAPI Application Entry Point

A Python FastAPI service that integrates with a Node.js backend,
providing LLM-powered task/event management with RAG capabilities.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("pixie")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info(
        "Starting Pixie AI Service",
        extra={"environment": settings.environment, "port": settings.port},
    )
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log Level: {settings.log_level}")

    yield

    # Shutdown
    logger.info("Shutting down Pixie AI Service")


app = FastAPI(
    title="Pixie AI Service",
    description="AI productivity assistant for task and event management",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


@app.get("/")
async def root():
    """Root endpoint - basic service status."""
    return {"service": "pixie-ai", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancer probes.

    Returns basic health status. In future steps, this will include
    dependency checks (Qdrant, Redis, etc.).
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors.

    Logs the error and returns a user-friendly message.
    Never exposes internal error details to clients.
    """
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )
