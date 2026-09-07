from __future__ import annotations

from typing import Any

from django.db import DatabaseError
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from . import repositories


def _limit(request: Request, *, default: int, maximum: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError({"limit": "Must be an integer."}) from exc
    if value < 1 or value > maximum:
        raise ValidationError({"limit": f"Must be between 1 and {maximum}."})
    return value


def _bool_query(request: Request, name: str, *, default: bool) -> bool:
    raw = request.query_params.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError({name: "Must be a boolean value."})


def _datetime_query(request: Request, name: str) -> Any | None:
    raw = request.query_params.get(name)
    if not raw:
        return None
    value = parse_datetime(raw)
    if value is None:
        raise ValidationError({name: "Must be a valid ISO-8601 datetime."})
    return value


def _heat_or_404(heat_no: str) -> dict[str, Any]:
    heat = repositories.heat_by_no(heat_no)
    if heat is None:
        raise NotFound(detail=f"Heat {heat_no} not found")
    return heat


@api_view(["GET"])
def health(request: Request) -> Response:
    del request
    try:
        repositories.ping_database()
    except DatabaseError as exc:
        return Response(
            {
                "detail": f"Database unavailable: {exc}",
                "status": "error",
                "service": "level2-api",
            },
            status=503,
        )

    return Response(
        {
            "status": "ok",
            "database": "reachable",
            "service": "level2-api",
            "framework": "django-rest-framework",
            "api_version": "v1",
        }
    )


@api_view(["GET"])
def api_meta(request: Request) -> Response:
    del request
    return Response(
        {
            "name": "Steelmaking Level 2 API",
            "version": "0.2.0",
            "api_version": "v1",
            "framework": "django-rest-framework",
            "process_flow": ["EAF", "LF", "CCM"],
            "capabilities": [
                "heat-read-model",
                "heat-overview",
                "equipment-master",
                "steel-grade-master",
                "event-query",
                "alarm-query",
                "historian-latest-values",
                "historian-tag-samples",
            ],
            "write_service": "heat-management",
        }
    )


@api_view(["GET"])
def list_heats(request: Request) -> Response:
    return Response(
        repositories.heats(
            status=request.query_params.get("status"),
            limit=_limit(request, default=50, maximum=500),
        )
    )


@api_view(["GET"])
def heat_detail(request: Request, heat_no: str) -> Response:
    del request
    return Response(_heat_or_404(heat_no))


@api_view(["GET"])
def heat_overview(request: Request, heat_no: str) -> Response:
    del request
    heat = _heat_or_404(heat_no)
    heat_id = heat["id"]
    return Response(
        {
            "heat": heat,
            "live_values": repositories.heat_live_values(heat_id),
            "material_summary": repositories.heat_material_summary(heat_id),
            "recent_events": repositories.heat_recent_events(heat_id),
            "active_alarms": repositories.heat_active_alarms(heat_id),
        }
    )


@api_view(["GET"])
def equipment(request: Request) -> Response:
    return Response(repositories.equipment(area=request.query_params.get("area")))


@api_view(["GET"])
def steel_grades(request: Request) -> Response:
    return Response(
        repositories.steel_grades(
            active_only=_bool_query(request, "active_only", default=True)
        )
    )


@api_view(["GET"])
def events(request: Request) -> Response:
    return Response(
        repositories.events(
            heat_no=request.query_params.get("heat_no"),
            event_type=request.query_params.get("event_type"),
            source_system=request.query_params.get("source_system"),
            limit=_limit(request, default=100, maximum=1000),
        )
    )


@api_view(["GET"])
def alarms(request: Request) -> Response:
    return Response(
        repositories.alarms(
            state=request.query_params.get("state"),
            severity=request.query_params.get("severity"),
            heat_no=request.query_params.get("heat_no"),
            limit=_limit(request, default=100, maximum=1000),
        )
    )


@api_view(["GET"])
def historian_latest(request: Request) -> Response:
    return Response(
        repositories.historian_latest(
            area=request.query_params.get("area"),
            equipment_code=request.query_params.get("equipment_code"),
            quality=request.query_params.get("quality"),
        )
    )


@api_view(["GET"])
def historian_tag_samples(request: Request, tag_name: str) -> Response:
    tag = repositories.historian_tag(tag_name)
    if tag is None:
        raise NotFound(detail=f"Tag {tag_name} not found")

    samples = repositories.historian_tag_samples(
        tag_name=tag_name,
        start=_datetime_query(request, "start"),
        end=_datetime_query(request, "end"),
        heat_no=request.query_params.get("heat_no"),
        limit=_limit(request, default=500, maximum=5000),
    )
    return Response({"tag": tag, "samples": samples})
