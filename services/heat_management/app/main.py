from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from fastapi import FastAPI, HTTPException, Query, status
from psycopg import Connection
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field


DB_HOST = os.getenv("DB_HOST", "historian-db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")

HEAT_STATUSES = {
    "PLANNED",
    "CREATED",
    "CHARGING",
    "EAF",
    "TAPPING",
    "LF",
    "CASTING",
    "HOLD",
    "COMPLETED",
    "ABORTED",
    "CANCELLED",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PLANNED": {"CREATED", "CANCELLED"},
    "CREATED": {"CHARGING", "EAF", "CANCELLED"},
    "CHARGING": {"EAF", "HOLD", "ABORTED"},
    "EAF": {"TAPPING", "HOLD", "ABORTED"},
    "TAPPING": {"LF", "HOLD", "ABORTED"},
    "LF": {"CASTING", "HOLD", "ABORTED"},
    "CASTING": {"COMPLETED", "HOLD", "ABORTED"},
    "HOLD": {"EAF", "LF", "CASTING", "ABORTED", "CANCELLED"},
    "COMPLETED": set(),
    "ABORTED": set(),
    "CANCELLED": set(),
}

app = FastAPI(
    title="Steelmaking Level 2 - Heat Management",
    version="0.1.0",
    description=(
        "Level 2 heat tracking and lifecycle API for EAF/LF/CCM. "
        "This service manages production state and history; it does not directly control Level 1 actuators."
    ),
)


class HeatCreate(BaseModel):
    heat_no: str = Field(min_length=1, max_length=64)
    grade_code: str = Field(default="DEMO-ST37", min_length=1, max_length=64)
    grade_revision: int = Field(default=1, ge=1)
    planned_weight_t: float | None = Field(default=None, gt=0)
    production_order_id: str | None = Field(default=None, max_length=128)
    planned_sequence: int | None = Field(default=None, ge=1)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=512)
    actor: str = Field(default="operator", min_length=1, max_length=128)


@contextmanager
def db_connection() -> Iterator[Connection]:
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=dict_row,
    )
    try:
        yield conn
    finally:
        conn.close()


def require_status(value: str) -> str:
    normalized = value.upper()
    if normalized not in HEAT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown heat status: {value}",
        )
    return normalized


def fetch_heat(conn: Connection, heat_no: str, *, for_update: bool = False) -> dict[str, Any]:
    locking = " FOR UPDATE" if for_update else ""
    row = conn.execute(
        f"""
        SELECT
            h.id,
            h.heat_no,
            h.status::text AS status,
            h.planned_weight_t,
            h.actual_weight_t,
            h.production_order_id,
            h.planned_sequence,
            h.attributes,
            h.created_at,
            h.started_at,
            h.completed_at,
            h.updated_at,
            sg.code AS grade_code,
            sg.revision AS grade_revision,
            sg.name AS grade_name
        FROM heats h
        LEFT JOIN steel_grades sg ON sg.id = h.grade_id
        WHERE h.heat_no = %s
        {locking}
        """,
        (heat_no,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Heat {heat_no} not found")
    return row


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with db_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "reachable", "service": "heat-management"}
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/heats")
def list_heats(
    heat_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if heat_status:
        normalized = require_status(heat_status)
        where = "WHERE h.status = %s::heat_status"
        params.append(normalized)
    params.append(limit)

    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t,
                h.actual_weight_t,
                h.production_order_id,
                h.created_at,
                h.started_at,
                h.completed_at,
                h.updated_at
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            {where}
            ORDER BY h.created_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return rows


@app.get("/heats/active")
def active_heats() -> list[dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t,
                h.actual_weight_t,
                h.production_order_id,
                h.started_at,
                h.updated_at
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            WHERE h.status NOT IN ('COMPLETED', 'ABORTED', 'CANCELLED')
            ORDER BY h.created_at DESC
            """
        ).fetchall()
    return rows


@app.get("/heats/{heat_no}")
def get_heat(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        return fetch_heat(conn, heat_no)


@app.get("/heats/{heat_no}/timeline")
def heat_timeline(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        heat = fetch_heat(conn, heat_no)
        stages = conn.execute(
            """
            SELECT
                hs.stage,
                e.code AS equipment_code,
                hs.status,
                hs.started_at,
                hs.ended_at,
                hs.attributes
            FROM heat_stages hs
            LEFT JOIN equipment e ON e.id = hs.equipment_id
            WHERE hs.heat_id = %s
            ORDER BY hs.started_at
            """,
            (heat["id"],),
        ).fetchall()
        events = conn.execute(
            """
            SELECT
                he.event_type,
                he.source_system,
                he.area,
                e.code AS equipment_code,
                he.severity,
                he.occurred_at,
                he.payload
            FROM heat_events he
            LEFT JOIN equipment e ON e.id = he.equipment_id
            WHERE he.heat_id = %s
            ORDER BY he.occurred_at
            """,
            (heat["id"],),
        ).fetchall()
    return {"heat_no": heat_no, "status": heat["status"], "stages": stages, "events": events}


@app.get("/heats/{heat_no}/live")
def heat_live_values(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        heat = fetch_heat(conn, heat_no)
        values = conn.execute(
            """
            SELECT DISTINCT ON (ps.tag_id)
                pt.tag_name,
                pt.engineering_unit,
                ps.value_double,
                ps.value_text,
                ps.quality::text AS quality,
                ps.ts
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            WHERE ps.heat_id = %s
            ORDER BY ps.tag_id, ps.ts DESC
            """,
            (heat["id"],),
        ).fetchall()
    return {"heat_no": heat_no, "status": heat["status"], "values": values}


@app.post("/heats", status_code=status.HTTP_201_CREATED)
def create_heat(payload: HeatCreate) -> dict[str, Any]:
    attributes = {**payload.attributes, "created_by": "heat-management-api"}
    try:
        with db_connection() as conn:
            with conn.transaction():
                grade = conn.execute(
                    """
                    SELECT id
                    FROM steel_grades
                    WHERE code = %s AND revision = %s AND is_active = TRUE
                    """,
                    (payload.grade_code, payload.grade_revision),
                ).fetchone()
                if not grade:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Steel grade {payload.grade_code} revision "
                            f"{payload.grade_revision} not found or inactive"
                        ),
                    )

                conn.execute(
                    """
                    INSERT INTO heats (
                        heat_no,
                        grade_id,
                        status,
                        planned_weight_t,
                        production_order_id,
                        planned_sequence,
                        attributes
                    )
                    VALUES (%s, %s, 'CREATED', %s, %s, %s, %s)
                    """,
                    (
                        payload.heat_no,
                        grade["id"],
                        payload.planned_weight_t,
                        payload.production_order_id,
                        payload.planned_sequence,
                        Jsonb(attributes),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO heat_events (
                        event_type,
                        source_system,
                        source_event_id,
                        heat_id,
                        severity,
                        occurred_at,
                        payload
                    )
                    SELECT
                        'HEAT_CREATED',
                        'LEVEL2_HEAT_MANAGEMENT',
                        %s,
                        id,
                        'INFO',
                        now(),
                        %s
                    FROM heats
                    WHERE heat_no = %s
                    """,
                    (
                        f"HM-{payload.heat_no}-CREATED-{datetime.now(timezone.utc).timestamp()}",
                        Jsonb({"actor": "heat-management-api"}),
                        payload.heat_no,
                    ),
                )
            return fetch_heat(conn, payload.heat_no)
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail=f"Heat {payload.heat_no} already exists") from exc


@app.post("/heats/{heat_no}/transition")
def transition_heat(heat_no: str, payload: TransitionRequest) -> dict[str, Any]:
    target = require_status(payload.target_status)

    with db_connection() as conn:
        with conn.transaction():
            heat = fetch_heat(conn, heat_no, for_update=True)
            current = heat["status"]
            allowed = ALLOWED_TRANSITIONS.get(current, set())
            if target not in allowed:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Invalid transition {current} -> {target}",
                        "current_status": current,
                        "allowed_targets": sorted(allowed),
                    },
                )

            completion_sql = ", completed_at = now()" if target == "COMPLETED" else ""
            start_sql = ", started_at = COALESCE(started_at, now())" if target in {"CHARGING", "EAF"} else ""
            conn.execute(
                f"""
                UPDATE heats
                SET status = %s::heat_status,
                    updated_at = now()
                    {start_sql}
                    {completion_sql}
                WHERE id = %s
                """,
                (target, heat["id"]),
            )
            conn.execute(
                """
                INSERT INTO heat_events (
                    event_type,
                    source_system,
                    source_event_id,
                    heat_id,
                    severity,
                    occurred_at,
                    payload
                )
                VALUES (
                    'STATUS_CHANGED',
                    'LEVEL2_HEAT_MANAGEMENT',
                    %s,
                    %s,
                    'INFO',
                    now(),
                    %s
                )
                """,
                (
                    f"HM-{heat_no}-{current}-{target}-{datetime.now(timezone.utc).timestamp()}",
                    heat["id"],
                    Jsonb(
                        {
                            "from": current,
                            "to": target,
                            "reason": payload.reason,
                            "actor": payload.actor,
                        }
                    ),
                ),
            )

        return fetch_heat(conn, heat_no)
