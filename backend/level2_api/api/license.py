from __future__ import annotations

import base64
import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAHFpgcga1SAUY+ShwCQjngxsuBFLAJUuqmoJLUqhB4B4=
-----END PUBLIC KEY-----
"""
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MUTATION_EXEMPT_PREFIXES = (
    "/health",
    "/api/v1/license",
    "/api/v1/auth/token",
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _decode_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expires_at is required")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _public_key() -> Ed25519PublicKey:
    loaded = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
    if not isinstance(loaded, Ed25519PublicKey):
        raise TypeError("Configured license public key is not Ed25519")
    return loaded


def _base_state(*, status: str, read_only: bool, message: str) -> dict[str, Any]:
    return {
        "status": status,
        "read_only": read_only,
        "message": message,
        "customer": None,
        "license_id": None,
        "product": "Steelmaking Level 2",
        "expires_at": None,
        "grace_ends_at": None,
        "days_remaining": None,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


def get_license_status(now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    token = os.getenv("LICENSE_TOKEN", "").strip()
    allow_unlicensed = _env_bool("LICENSE_ALLOW_UNLICENSED", True)

    if not token:
        if allow_unlicensed:
            return _base_state(
                status="DEVELOPMENT",
                read_only=False,
                message="License enforcement is disabled for this environment.",
            )
        return _base_state(
            status="READ_ONLY",
            read_only=True,
            message="No valid license is installed. The system is in read-only mode.",
        )

    try:
        payload_segment, signature_segment = token.split(".", 1)
        payload_bytes = _decode_segment(payload_segment)
        signature = _decode_segment(signature_segment)
        _public_key().verify(signature, payload_bytes)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("License payload must be an object")

        expires_at = _parse_datetime(payload.get("expires_at"))
        grace_days = max(0, int(payload.get("grace_days", 7)))
        grace_ends_at = expires_at + timedelta(days=grace_days)
        customer = str(payload.get("customer") or "Licensed customer")
        license_id = str(payload.get("license_id") or "") or None
        product = str(payload.get("product") or "Steelmaking Level 2")

        if current <= expires_at:
            remaining_seconds = max(0.0, (expires_at - current).total_seconds())
            state = "ACTIVE"
            read_only = False
            message = "License active. Full operational access is enabled."
            days_remaining = math.ceil(remaining_seconds / 86400)
        elif current <= grace_ends_at:
            remaining_seconds = max(0.0, (grace_ends_at - current).total_seconds())
            state = "GRACE"
            read_only = False
            message = "License expired; grace period is active. Renew before read-only mode begins."
            days_remaining = math.ceil(remaining_seconds / 86400)
        else:
            state = "READ_ONLY"
            read_only = True
            message = "License and grace period expired. Monitoring remains available in read-only mode."
            days_remaining = 0

        return {
            "status": state,
            "read_only": read_only,
            "message": message,
            "customer": customer,
            "license_id": license_id,
            "product": product,
            "expires_at": expires_at.isoformat(),
            "grace_ends_at": grace_ends_at.isoformat(),
            "days_remaining": days_remaining,
            "server_time": current.isoformat(),
        }
    except (ValueError, TypeError, json.JSONDecodeError, InvalidSignature, UnicodeDecodeError):
        return _base_state(
            status="INVALID",
            read_only=True,
            message="The installed license is invalid. The system is in read-only mode.",
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def license_status(request) -> Response:
    del request
    return Response(get_license_status())


class LicenseReadOnlyMiddleware:
    """Block mutating Django requests after signed license expiry without hiding data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method.upper() in SAFE_METHODS:
            return self.get_response(request)
        if request.path.startswith(MUTATION_EXEMPT_PREFIXES):
            return self.get_response(request)

        license_state = get_license_status()
        if license_state["read_only"]:
            return JsonResponse(
                {
                    "code": "LICENSE_READ_ONLY",
                    "detail": license_state["message"],
                    "license": license_state,
                },
                status=423,
            )
        return self.get_response(request)
