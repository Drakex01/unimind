"""UniMind Core API Application Entrypoint."""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from plugin_sdk.registry import PluginRegistry
from provider_contracts.gateway import ModelGateway
from provider_contracts.mock_provider import MockModelProvider
from .core.config import settings
from .core.database import init_db
from .routers import chat, health, plugins

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.unimind_log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("unimind.api")


def setup_dependencies() -> tuple[PluginRegistry, ModelGateway]:
    """Initialize plugin registry and model gateway."""
    registry = PluginRegistry()
    plugins_dir = Path(settings.plugins_dir)
    registry.discover_and_load(plugins_dir)
    plugins.set_plugin_registry(registry)

    gateway = ModelGateway()
    mock_provider = MockModelProvider(
        provider_name="mock-provider",
        model_id="mock-model-v1",
    )
    gateway.register_provider(mock_provider)
    chat.set_model_gateway(gateway)
    return registry, gateway


# Initialize state so handlers and ASGI transports have dependencies available
_registry, _gateway = setup_dependencies()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Initializing UniMind database schema...")
    await init_db()
    logger.info(f"UniMind API ready. Loaded {len(_registry.list_plugins())} plugins.")
    yield
    logger.info("UniMind API shutting down.")


app = FastAPI(
    title="UniMind Core API",
    description="Adaptive Multimodal Foundation-Model Platform for Cross-Domain Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Enforce request correlation ID across all endpoints."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.correlation_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# Mount Routers
app.include_router(health.router)
app.include_router(plugins.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {
        "service": "UniMind Core API",
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs",
    }
