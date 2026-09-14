from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import ADMINISTRATOR
from .rbac import PERMISSION_LABELS
from .rbac import ROLE_LABELS
from .rbac import assign_role
from .rbac import normalize_role
from .rbac import permissions_for_user
from .rbac import require_app_permission
from .rbac import role_catalog
from .rbac import role_for_user


def _user_payload(user) -> dict[str, object]:
    role = role_for_user(user)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "display_name": user.get_full_name().strip() or user.get_username(),
        "role": role,
        "role_label": ROLE_LABELS[role],
        "permissions": sorted(permissions_for_user(user)),
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _role(value: object) -> str:
    try:
        return normalize_role(value)
    except ValueError as exc:
        raise ValidationError({"role": str(exc)}) from exc


def _password(value: object, *, required: bool) -> str | None:
    password = str(value or "")
    if not password and not required:
        return None
    if len(password) < 8:
        raise ValidationError({"password": "Password must contain at least 8 characters."})
    return password


def _boolean(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValidationError({field: "This field must be a boolean."})


@api_view(["GET"])
def roles(request: Request) -> Response:
    require_app_permission(request.user, "users.manage")
    return Response(
        {
            "roles": list(role_catalog()),
            "permission_labels": dict(sorted(PERMISSION_LABELS.items())),
        }
    )


@api_view(["GET", "POST"])
def users(request: Request) -> Response:
    require_app_permission(request.user, "users.manage")
    user_model = get_user_model()

    if request.method == "GET":
        records = user_model.objects.prefetch_related("groups").order_by("username")
        return Response({"users": [_user_payload(user) for user in records]})

    username = str(request.data.get("username", "")).strip()
    display_name = str(request.data.get("display_name", "")).strip()
    role = _role(request.data.get("role", "VIEWER"))
    password = _password(request.data.get("password"), required=True)
    if not username:
        raise ValidationError({"username": "Username is required."})
    if user_model.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "A user with this username already exists."})

    with transaction.atomic():
        user = user_model.objects.create_user(
            username=username,
            password=password,
            first_name=display_name,
            is_active=_boolean(request.data.get("is_active", True), field="is_active"),
        )
        assign_role(user, role)
    return Response(_user_payload(user), status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
def user_detail(request: Request, user_id: int) -> Response:
    require_app_permission(request.user, "users.manage")
    user_model = get_user_model()
    try:
        user = user_model.objects.prefetch_related("groups").get(pk=user_id)
    except user_model.DoesNotExist as exc:
        raise NotFound("User not found.") from exc

    role = _role(request.data.get("role", role_for_user(user)))
    is_active = _boolean(request.data.get("is_active", user.is_active), field="is_active")
    if user.pk == request.user.pk and (role != ADMINISTRATOR or not is_active):
        raise ValidationError("You cannot remove your own administrator access or deactivate your own account.")

    password = _password(request.data.get("password"), required=False)
    with transaction.atomic():
        if "display_name" in request.data:
            user.first_name = str(request.data.get("display_name", "")).strip()
        user.is_active = is_active
        if password:
            user.set_password(password)
        user.save()
        assign_role(user, role)
    return Response(_user_payload(user))
