"""Web PubSub token endpoint exposed at /pubsub/*."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.auth import require_auth
from backend.app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pubsub", tags=["PubSub"])



class TokenRequest(BaseModel):
    user_id: str    = Field(..., max_length=128, description="Unique participant identifier.")
    session_id: str = Field(..., max_length=128, description="Meeting session / room identifier.")


class TokenResponse(BaseModel):
    url: str
    token: str
    user_id: str
    hub: str



@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue a Web PubSub WebSocket access token",
)
@limiter.limit("60/minute")
async def get_pubsub_token(
    request: Request,
    body: TokenRequest,
    _claims: dict = Depends(require_auth),
) -> TokenResponse:
    """
    Returns a short-lived Azure Web PubSub client access token.
    The browser uses the returned `url` to open a WebSocket connection.
    """
    hub = getattr(request.app.state, "hub", None)
    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HubManager not initialised.",
        )

    try:
        result = hub.get_client_token(
            user_id=body.user_id,
            session_id=body.session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return TokenResponse(
        url=result["url"],
        token=result["token"],
        user_id=result["user_id"],
        hub=result["hub"],
    )
