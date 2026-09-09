from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class JwtAuthenticationTests(APITestCase):
    username = "OP-4109"
    password = "test-password-1405"

    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username=self.username,
            password=self.password,
            first_name="اپراتور تست",
        )

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
                "display_name": "اپراتور تست",
                "is_staff": False,
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
