from __future__ import annotations

from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

from level2_project.asgi import application


class TelemetryWebsocketTests(SimpleTestCase):
    async def test_connection_without_jwt_subprotocol_is_rejected(self) -> None:
        communicator = WebsocketCommunicator(application, "/ws/v1/telemetry")

        connected, _ = await communicator.connect()

        self.assertFalse(connected)

    async def test_authenticated_connection_receives_snapshot(self) -> None:
        snapshot = {
            "server_time": "2026-09-09T06:00:00Z",
            "active_heat": {"heat_no": "SIM-H1", "status": "EAF"},
            "live_values": [],
            "active_alarms": [],
            "recent_events": [],
            "l1_link": {
                "online": True,
                "age_seconds": 0.4,
                "last_sample_at": "2026-09-09T05:59:59Z",
            },
        }

        with (
            patch(
                "api.consumers._authenticate_access_token",
                new=AsyncMock(return_value=object()),
            ),
            patch("api.consumers._snapshot", new=AsyncMock(return_value=snapshot)),
        ):
            communicator = WebsocketCommunicator(
                application,
                "/ws/v1/telemetry",
                subprotocols=["level2.jwt", "test-access-token"],
            )

            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)
            self.assertEqual(subprotocol, "level2.jwt")

            message = await communicator.receive_json_from(timeout=1)
            self.assertEqual(message["type"], "telemetry.snapshot")
            self.assertEqual(message["data"]["active_heat"]["heat_no"], "SIM-H1")

            await communicator.disconnect()
