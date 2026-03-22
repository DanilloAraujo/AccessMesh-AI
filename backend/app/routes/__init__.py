"""
backend/app/routes

Defines the API routes for the backend application. 
Each route module corresponds to a specific area of functionality (e.g., chat, gestures, speech) and contains the FastAPI route definitions and handlers for that area.

"""

from .chat_routes import router as chat_router
from .gesture_routes import router as gesture_router
from .hub_routes import router as hub_router
from .pubsub_routes import router as pubsub_router
from .speech_routes import router as speech_router

__all__ = ["speech_router", "chat_router", "gesture_router", "pubsub_router", "hub_router"]
