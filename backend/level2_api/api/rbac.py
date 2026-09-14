from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.contrib.auth.models import Group
from rest_framework.exceptions import PermissionDenied


ADMINISTRATOR = "ADMINISTRATOR"
AUTOMATION_ENGINEER = "AUTOMATION_ENGINEER"
SHIFT_SUPERVISOR = "SHIFT_SUPERVISOR"
OPERATOR = "OPERATOR"
VIEWER = "VIEWER"

ROLE_LABELS = {
    ADMINISTRATOR: "Administrator",
    AUTOMATION_ENGINEER: "Automation Engineer",
    SHIFT_SUPERVISOR: "Shift Supervisor",
    OPERATOR: "Operator",
    VIEWER: "Viewer",
}

PERMISSION_LABELS = {
    "overview.view": "View operations overview",
    "production.view": "View live production flow",
    "historian.view": "View historian data",
    "alarms.view": "View process alarms",
    "alarms.acknowledge": "Acknowledge process alarms",
    "reports.view": "View reports and analytics",
    "plc.diagnostics": "View PLC and system diagnostics",
    "configuration.view": "View system configuration",
    "configuration.manage": "Manage system configuration",
    "users.manage": "Manage users and roles",
}

ROLE_PERMISSIONS = {
    VIEWER: {"overview.view", "production.view"},
    OPERATOR: {
        "overview.view",
        "production.view",
        "historian.view",
        "alarms.view",
    },
    SHIFT_SUPERVISOR: {
        "overview.view",
        "production.view",
        "historian.view",
        "alarms.view",
        "alarms.acknowledge",
        "reports.view",
    },
    AUTOMATION_ENGINEER: {
        "overview.view",
        "production.view",
        "historian.view",
        "alarms.view",
        "plc.diagnostics",
        "configuration.view",
    },
    ADMINISTRATOR: set(PERMISSION_LABELS),
}

ROLE_PRIORITY = (
    ADMINISTRATOR,
    AUTOMATION_ENGINEER,
    SHIFT_SUPERVISOR,
    OPERATOR,
    VIEWER,
)


def group_name(role: str) -> str:
    return f"Level2:{role}"


def normalize_role(value: object) -> str:
    role = str(value or "").strip().upper().replace(" ", "_")
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Unknown role: {value}")
    return role


def ensure_role_groups() -> None:
    for role in ROLE_PRIORITY:
        Group.objects.get_or_create(name=group_name(role))


def role_for_user(user: Any) -> str:
    if user.is_superuser:
        return ADMINISTRATOR
    memberships = set(user.groups.values_list("name", flat=True))
    for role in ROLE_PRIORITY:
        if group_name(role) in memberships:
            return role
    return VIEWER


def permissions_for_user(user: Any) -> set[str]:
    return set(ROLE_PERMISSIONS[role_for_user(user)])


def has_app_permission(user: Any, permission: str) -> bool:
    return bool(user.is_authenticated and permission in permissions_for_user(user))


def require_app_permission(user: Any, permission: str) -> None:
    if not has_app_permission(user, permission):
        raise PermissionDenied(f"Your role does not include the '{permission}' permission.")


def assign_role(user: Any, role: str) -> None:
    normalized = normalize_role(role)
    ensure_role_groups()
    managed_names = [group_name(item) for item in ROLE_PRIORITY]
    user.groups.remove(*Group.objects.filter(name__in=managed_names))
    user.groups.add(Group.objects.get(name=group_name(normalized)))


def role_catalog() -> Iterable[dict[str, object]]:
    for role in ROLE_PRIORITY:
        yield {
            "key": role,
            "label": ROLE_LABELS[role],
            "permissions": sorted(ROLE_PERMISSIONS[role]),
        }
