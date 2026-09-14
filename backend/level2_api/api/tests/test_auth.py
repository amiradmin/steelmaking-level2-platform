from __future__ import annotations

from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from api.rbac import AUTOMATION_ENGINEER, OPERATOR, ROLE_LABELS, ROLE_PERMISSIONS, assign_role


class JwtAuthenticationTests(APITestCase):
    username = "OP-4109"
    password = "test-password-1405"

    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username=self.username,
            password=self.password,
            first_name="Test Operator",
        )
        assign_role(self.user, OPERATOR)

    def obtain_tokens(self) -> dict[str, str]:
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"username": self.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_valid_credentials_return_access_and_refresh_tokens(self) -> None:
        tokens = self.obtain_tokens()

        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)

    def test_invalid_credentials_are_rejected(self) -> None:
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"username": self.username, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_operational_api_requires_jwt(self) -> None:
        response = self.client.get(reverse("api-meta"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_operator_can_read_profile_and_api(self) -> None:
        access_token = self.obtain_tokens()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        profile_response = self.client.get(reverse("current-user"))
        meta_response = self.client.get(reverse("api-meta"))

        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            profile_response.json(),
            {
                "username": self.username,
                "display_name": "Test Operator",
                "is_staff": False,
                "role": OPERATOR,
                "role_label": ROLE_LABELS[OPERATOR],
                "permissions": sorted(ROLE_PERMISSIONS[OPERATOR]),
            },
        )
        self.assertEqual(meta_response.status_code, status.HTTP_200_OK)

    def test_refresh_token_returns_new_access_token(self) -> None:
        refresh_token = self.obtain_tokens()["refresh"]

        response = self.client.post(
            reverse("token-refresh"),
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_live_system_map_requires_jwt_and_returns_flow_health(self) -> None:
        unauthenticated = self.client.get(reverse("live-system-map"))
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        restricted_token = self.obtain_tokens()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {restricted_token}")
        restricted_response = self.client.get(reverse("live-system-map"))
        self.assertEqual(restricted_response.status_code, status.HTTP_403_FORBIDDEN)

        administrator = get_user_model().objects.create_user(
            username="automation-engineer",
            password="administrator-test-password",
        )
        assign_role(administrator, AUTOMATION_ENGINEER)
        administrator_token = self.client.post(
            reverse("token-obtain-pair"),
            {"username": administrator.username, "password": "administrator-test-password"},
            format="json",
        ).json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {administrator_token}")
        now = datetime.now(timezone.utc)
        controller_samples = {
            "eaf": {"last_sample_at": now, "samples_last_window": 12},
            "lf": {"last_sample_at": now, "samples_last_window": 11},
            "ccm": {"last_sample_at": now, "samples_last_window": 10},
        }

        with (
            patch("api.system_map._latest_controller_samples", return_value=controller_samples),
            patch("api.system_map._latest_opcua_sample", return_value=now),
            patch("api.system_map._service_health", return_value=True),
        ):
            response = self.client.get(reverse("live-system-map"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(len(payload["nodes"]), 10)
        self.assertEqual(len(payload["flows"]), 9)
        self.assertEqual(payload["nodes"][0]["status"], "online")
        self.assertEqual(payload["flows"][3]["label"], "OPC UA")

    def test_live_production_flow_is_available_to_every_authenticated_user(self) -> None:
        unauthenticated = self.client.get(reverse("production-flow"))
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        access_token = self.obtain_tokens()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        snapshot = {
            "active_heat": {
                "id": "1d2a89d1-6d54-4eb6-9aa0-8c3af0c761ea",
                "heat_no": "SIM-H-001",
                "status": "LF",
            },
            "live_values": [
                {"tag_name": "LF.SteelTemperature", "value_double": 1588.0, "engineering_unit": "degC", "quality": "GOOD", "ts": datetime.now(timezone.utc)},
                {"tag_name": "LF.ArgonFlow", "value_double": 122.0, "engineering_unit": "Nm3/h", "quality": "GOOD", "ts": datetime.now(timezone.utc)},
            ],
            "l1_link": {"online": True, "age_seconds": 1.0, "last_sample_at": datetime.now(timezone.utc)},
        }
        with (
            patch("api.production_flow.build_dashboard_snapshot", return_value=snapshot),
            patch("api.production_flow._active_stage", return_value={"stage": "LF", "area": "LF", "started_at": datetime.now(timezone.utc), "equipment_code": "LF-01"}),
            patch("api.production_flow._current_run_started_at", return_value=None),
        ):
            response = self.client.get(reverse("production-flow"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["current_heat"]["heat_no"], "SIM-H-001")
        self.assertEqual(payload["stations"][1]["state"], "active")
        self.assertEqual(payload["stations"][2]["state"], "ready")
