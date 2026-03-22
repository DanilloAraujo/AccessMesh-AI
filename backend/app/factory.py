"""FastAPI application factory for AccessMesh-AI."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.accessibility_agent import AccessibilityAgent
from agents.avatar_agent import AvatarAgent
from agents.gesture_agent import GestureAgent
from agents.pipeline import AgentMeshPipeline
from agents.speech_agent import SpeechAgent
from agents.router_agent import RouterAgent
from agents.summary_agent import SummaryAgent
from agents.translation_agent import TranslationAgent
from shared.config import settings
from backend.app.core.hub_manager import HubManager
from backend.app.core.realtime_dispatcher import RealtimeDispatcher
from backend.app.message_router import MessageRouter
from services.gesture_service import GestureService
from services.speech_service import SpeechService
from services.summarization_service import SummarizationService
from services.webpubsub_service import WebPubSubService
from services.cosmos_service import CosmosService
from services.content_safety_service import ContentSafetyService
from services.translator_service import TranslatorService
from services.telemetry_service import TelemetryService
from services.servicebus_service import ServiceBusService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Suppress verbose HTTP-level logs from Azure SDKs — only expose warnings and above.
for _noisy in (
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.cosmos._cosmos_http_logging_policy",
    "azure.monitor.opentelemetry",
    "azure.monitor.opentelemetry.exporter",
    "azure.monitor.opentelemetry.exporter.export._base",
    "azure.monitor.opentelemetry.exporter._quickpulse",
    "opentelemetry",
    # Suppress per-frame AMQP protocol traces from the Service Bus SDK.
    "azure.servicebus._pyamqp",
    "azure.servicebus._pyamqp.aio._connection_async",
    "azure.servicebus._pyamqp.aio._session_async",
    "azure.servicebus._pyamqp.aio._link_async",
    "azure.servicebus._pyamqp.aio._management_link_async",
    "azure.servicebus._pyamqp.aio._cbs_async",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



def create_app() -> FastAPI:
    """Build and return the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("[START] AccessMesh-AI backend starting...")

        # ── Azure Application Insights ──────────────────────────────────
        app.state.telemetry = TelemetryService()
        logger.info(
            "[OK] TelemetryService — App Insights: %s",
            "enabled" if app.state.telemetry.is_enabled else "disabled (set APPINSIGHTS_CONNECTION_STRING)",
        )

        # ── Azure Web PubSub ────────────────────────────────────────────
        app.state.pubsub = WebPubSubService()
        logger.info(
            "[OK] WebPubSubService — hub '%s': %s",
            settings.webpubsub_hub_name,
            "connected" if app.state.pubsub.is_enabled else "disabled (set WEBPUBSUB_CONNECTION_STRING)",
        )
        # ── Azure Service Bus ────────────────────────────────────────────────
        app.state.servicebus = ServiceBusService()
        logger.info(
            "[OK] ServiceBusService — topic '%s': %s",
            settings.servicebus_topic_name,
            "connected" if app.state.servicebus.is_enabled else "disabled (set SERVICEBUS_CONNECTION_STRING)",
        )
        # ── Azure Speech ────────────────────────────────────────────────
        app.state.speech = SpeechService()
        logger.info(
            "[OK] SpeechService — %s",
            f"region: {settings.azure_speech_region}" if app.state.speech.is_enabled
            else "disabled (set AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)",
        )

        # ── Azure Cosmos DB ─────────────────────────────────────────────
        app.state.cosmos = CosmosService()
        await app.state.cosmos.initialize()
        logger.info(
            "[OK] CosmosService — persistence: %s",
            "enabled" if app.state.cosmos.is_enabled else "in-memory (set COSMOS_ENDPOINT + COSMOS_KEY)",
        )

        # ── Azure Content Safety ────────────────────────────────────────
        app.state.content_safety = ContentSafetyService()
        logger.info(
            "[OK] ContentSafetyService — moderation: %s",
            "enabled" if app.state.content_safety.is_enabled else "disabled (set CONTENT_SAFETY_ENDPOINT + CONTENT_SAFETY_KEY)",
        )

        # ── Azure AI Translator ─────────────────────────────────────────
        app.state.translator = TranslatorService()
        logger.info(
            "[OK] TranslatorService — dedicated translation: %s",
            "enabled" if app.state.translator.is_enabled else "disabled (set TRANSLATOR_KEY)",
        )

        # ── Gesture + Summarization ────────────────────────────────────
        app.state.gesture = GestureService()
        logger.info(
            "[OK] GestureService ready — model: %s",
            "azure_openai" if settings.gesture_api_endpoint else "stub",
        )

        app.state.summarization = SummarizationService()
        logger.info(
            "[OK] SummarizationService ready — LLM: %s",
            "azure_openai" if settings.openai_key else "stub",
        )

        app.state.hub        = HubManager(pubsub=app.state.pubsub, cosmos=app.state.cosmos)
        app.state.dispatcher = RealtimeDispatcher(pubsub=app.state.pubsub)

        # Agent Mesh (true bus-based architecture)
        from agents import agent_bus, agent_registry
        from mcp.mcp_client import mcp_client

        _router_agent      = RouterAgent()
        _access_agent      = AccessibilityAgent(mcp_client=mcp_client)
        _translation_agent = TranslationAgent()
        _avatar_agent      = AvatarAgent(mcp_client=mcp_client)
        _gesture_agent     = GestureAgent()
        _summary_agent     = SummaryAgent()
        _speech_agent      = SpeechAgent(mcp_client=mcp_client)

        # Register agents in the service-discovery registry (for API routes)
        agent_registry.register("router_agent",        _router_agent)
        agent_registry.register("accessibility_agent", _access_agent)
        agent_registry.register("translation_agent",   _translation_agent)
        agent_registry.register("avatar_agent",        _avatar_agent)
        agent_registry.register("gesture_agent",       _gesture_agent)
        agent_registry.register("summary_agent",       _summary_agent)
        agent_registry.register("speech_agent",        _speech_agent)

        # Subscribe every agent to the bus according to its declared
        # ``subscribes_to`` list — this is the only wiring needed.
        # No agent holds a reference to any other agent.
        for _agent in (_router_agent, _access_agent, _translation_agent,
                       _avatar_agent, _gesture_agent, _summary_agent,
                       _speech_agent):
            _agent.register(agent_bus)

        # Start the agent bus — launches SB receive loops when SB is enabled
        await agent_bus.start(sb_service=app.state.servicebus)

        logger.info(
            "[OK] AgentMesh wired — registry=%s  bus_subscriptions=%s",
            agent_registry.list_names(),
            {k.value: len(v) for k, v in agent_bus._subscribers.items()},
        )

        # Store summary_agent on app.state so speech_routes can call
        # generate_meeting_minutes() via the accumulated bus store
        app.state.summary_agent = _summary_agent

        app.state.pipeline = AgentMeshPipeline(
            bus=agent_bus,
            pubsub_service=app.state.pubsub,
            telemetry=app.state.telemetry,
        )

        app.state.message_router = MessageRouter(
            pipeline=app.state.pipeline,
            gesture_svc=app.state.gesture,
            dispatcher=app.state.dispatcher,
            content_safety=app.state.content_safety,
        )

        logger.info("[OK] All services initialised.")
        yield

        logger.info("[STOP] AccessMesh-AI backend shutting down.")
        await agent_bus.stop()
        app.state.pubsub          = None
        app.state.speech          = None
        app.state.gesture         = None
        app.state.summarization   = None
        app.state.pipeline        = None
        app.state.hub             = None
        app.state.dispatcher      = None
        app.state.message_router  = None
        if app.state.cosmos:
            await app.state.cosmos.close()
        app.state.cosmos          = None
        app.state.content_safety  = None
        app.state.translator      = None
        app.state.telemetry       = None


    application = FastAPI(
        title="AccessMesh-AI",
        description=(
            "Real-time accessible communication hub. "
            "Multimodal input (voice / gesture / text) → AI agents → "
            "accessibility enrichment → live broadcast to all participants."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )


    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request tracing (X-Request-ID) ──────────────────────────────────────
    from backend.app.middleware import RequestTracingMiddleware
    application.add_middleware(RequestTracingMiddleware)

    # ── Rate limiting ───────────────────────────────────────────────────────
    try:
        from typing import cast as _cast, Callable as _Callable
        from slowapi import _rate_limit_exceeded_handler  # type: ignore[import]
        from slowapi.errors import RateLimitExceeded
        from starlette.types import ExceptionHandler as _ExceptionHandler
        from backend.app.limiter import limiter

        application.state.limiter = limiter
        application.add_exception_handler(
            RateLimitExceeded,
            _cast(_ExceptionHandler, _rate_limit_exceeded_handler),
        )
        logger.info("[OK] Rate limiting enabled (slowapi)")
    except ImportError:
        logger.warning("[WARN] slowapi not installed — rate limiting disabled.")

    from backend.app.routes import chat_router, gesture_router, pubsub_router
    from backend.app.routes import hub_router
    from backend.app.routes import speech_router as app_speech_router
    from backend.app.routes.auth_routes import router as auth_router

    application.include_router(auth_router)
    application.include_router(app_speech_router)
    application.include_router(chat_router)
    application.include_router(gesture_router)
    application.include_router(pubsub_router)
    application.include_router(hub_router)


    try:
        from mcp.mcp_server import mcp_app  # type: ignore[import]
        application.mount("/mcp", mcp_app)
        logger.info("[OK] MCP server mounted at /mcp")
    except Exception as _mcp_exc:
        logger.warning("[WARN] MCP server unavailable — continuing without it: %s", _mcp_exc)


    @application.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "service": "AccessMesh-AI Backend",
            "version": application.version,
            "status": "online",
            "docs": "/docs",
        }

    @application.get("/health", tags=["Health"])
    async def health() -> dict:
        pubsub = getattr(application.state, "pubsub", None)
        speech = getattr(application.state, "speech", None)
        cosmos = getattr(application.state, "cosmos", None)
        content_safety = getattr(application.state, "content_safety", None)
        translator = getattr(application.state, "translator", None)
        telemetry = getattr(application.state, "telemetry", None)
        return {
            "status": "ok",
            "services": {
                "webpubsub":        "connected"   if (pubsub and pubsub.is_enabled)           else "disconnected",
                "speech":           "configured"  if (speech and speech.is_enabled)            else "not_configured",
                "gesture":          "ready",
                "pipeline":         "ready"        if application.state.pipeline               else "not_ready",
                "hub_manager":      "ready"        if application.state.hub                    else "not_ready",
                "dispatcher":       "ready"        if application.state.dispatcher             else "not_ready",
                "message_router":   "ready"        if application.state.message_router         else "not_ready",
                "cosmos_db":        "enabled"      if (cosmos and cosmos.is_enabled)            else "in_memory",
                "content_safety":   "enabled"      if (content_safety and content_safety.is_enabled) else "disabled",
                "translator":       "enabled"      if (translator and translator.is_enabled)    else "disabled",
                "app_insights":     "enabled"      if (telemetry and telemetry.is_enabled)      else "disabled",
            },
        }

    return application
