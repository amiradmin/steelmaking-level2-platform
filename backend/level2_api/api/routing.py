from __future__ import annotations

from django.urls import path

from .consumers import TelemetryConsumer


websocket_urlpatterns = [
    path("ws/v1/telemetry", TelemetryConsumer.as_asgi(), name="ws-telemetry"),
]
