from __future__ import annotations

import asyncio
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

from .telemetry import build_dashboard_snapshot


JWT_SUBPROTOCOL = "level2.jwt"


@database_sync_to_async
def _authenticate_access_token(raw_token: str):
    authentication = JWTAuthentication()
    validated_token = authentication.get_validated_token(raw_token)
    return authentication.get_user(validated_token)


@database_sync_to_async
def _snapshot() -> dict:
    return build_dashboard_snapshot(
        stale_after_seconds=settings.TELEMETRY_STALE_AFTER_SECONDS,
    )


class TelemetryConsumer(AsyncWebsocketConsumer):
    """JWT-authenticated realtime dashboard stream.

    The browser sends the access token as the second websocket subprotocol so
    it is not exposed in the request URL or normal reverse-proxy access logs.
    """

    stream_task: asyncio.Task | None = None

    async def connect(self) -> None:
        subprotocols = list(self.scope.get("subprotocols", []))
        if len(subprotocols) < 2 or subprotocols[0] != JWT_SUBPROTOCOL:
            await self.close(code=4401)
            return

        try:
            user = await _authenticate_access_token(subprotocols[1])
        except (AuthenticationFailed, InvalidToken):
            await self.close(code=4401)
            return

        self.scope["user"] = user
        await self.accept(subprotocol=JWT_SUBPROTOCOL)
        self.stream_task = asyncio.create_task(self._stream_loop())

    async def disconnect(self, close_code: int) -> None:
        del close_code
        if self.stream_task is not None:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
            self.stream_task = None

    async def _stream_loop(self) -> None:
        interval = max(0.25, float(settings.TELEMETRY_PUSH_INTERVAL_SECONDS))
        while True:
            try:
                snapshot = await _snapshot()
                payload = {
                    "type": "telemetry.snapshot",
                    "data": snapshot,
                }
                await self.send(
                    text_data=json.dumps(payload, cls=DjangoJSONEncoder),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # keep the socket alive through transient DB errors
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "telemetry.error",
                            "detail": str(exc),
                        }
                    )
                )
            await asyncio.sleep(interval)
