from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.rbac import ADMINISTRATOR
from api.rbac import AUTOMATION_ENGINEER
from api.rbac import OPERATOR
from api.rbac import ROLE_PRIORITY
from api.rbac import VIEWER
from api.rbac import assign_role
from api.rbac import role_for_user


class AccessControlTests(APITestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.administrator = user_model.objects.create_user(
            username="admin-test",
            password="admin-password-1405",
            first_name="Test Administrator",
        )
        assign_role(self.administrator, ADMINISTRATOR)
        self.operator = user_model.objects.create_user(
            username="operator-test",
            password="operator-password-1405",
        )
        assign_role(self.operator, OPERATOR)

    def test_only_administrator_can_list_access_roles(self) -> None:
        self.client.force_authenticate(self.operator)
        denied = self.client.get(reverse("access-roles"))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.administrator)
        response = self.client.get(reverse("access-roles"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [role["key"] for role in response.json()["roles"]],
            list(ROLE_PRIORITY),
        )

    def test_administrator_can_create_and_promote_user(self) -> None:
        self.client.force_authenticate(self.administrator)
        created = self.client.post(
            reverse("access-users"),
            {
                "username": "plc-engineer",
                "display_name": "PLC Engineer",
                "password": "engineer-password-1405",
                "role": OPERATOR,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.json()["role"], OPERATOR)

        updated = self.client.patch(
            reverse("access-user-detail", args=[created.json()["id"]]),
            {"role": AUTOMATION_ENGINEER},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.json()["role"], AUTOMATION_ENGINEER)
        user = get_user_model().objects.get(username="plc-engineer")
        self.assertEqual(role_for_user(user), AUTOMATION_ENGINEER)

    def test_administrator_cannot_demote_or_deactivate_self(self) -> None:
        self.client.force_authenticate(self.administrator)
        response = self.client.patch(
            reverse("access-user-detail", args=[self.administrator.pk]),
            {"role": OPERATOR, "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_automation_engineer_can_open_system_map(self) -> None:
        engineer = get_user_model().objects.create_user(username="engineer-test")
        assign_role(engineer, AUTOMATION_ENGINEER)
        self.client.force_authenticate(engineer)

        from datetime import datetime, timezone
        from unittest.mock import patch

        now = datetime.now(timezone.utc)
        controller_samples = {
            "eaf": {"last_sample_at": now, "samples_last_window": 1},
            "lf": {"last_sample_at": now, "samples_last_window": 1},
            "ccm": {"last_sample_at": now, "samples_last_window": 1},
        }
        with (
            patch("api.system_map._latest_controller_samples", return_value=controller_samples),
            patch("api.system_map._latest_opcua_sample", return_value=now),
            patch("api.system_map._service_health", return_value=True),
        ):
            response = self.client.get(reverse("live-system-map"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_viewer_cannot_read_historian_alarms_or_plc_configuration(self) -> None:
        viewer = get_user_model().objects.create_user(username="viewer-test")
        assign_role(viewer, VIEWER)
        self.client.force_authenticate(viewer)

        self.assertEqual(
            self.client.get(reverse("historian-latest")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(reverse("alarms")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(reverse("plc-sources")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
