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
    version="0.2.1",
    description=(
        "Level 2 heat tracking, lifecycle and material-consumption API for EAF/LF/CCM. "
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


class MaterialAddition(BaseModel):
    material_code: str = Field(min_length=1, max_length=128)
    material_name: str | None = Field(default=None, max_length=255)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    equipment_code: str | None = Field(default=None, max_length=128)
    source_system: str = Field(default="LEVEL2_MATERIAL_TRACKING", min_length=1, max_length=64)
    batch_no: str | None = Field(default=None, max_length=128)
    addition_time: datetime | None = None
    actor: str = Field(default="operator", min_length=1, max_length=128)
    attributes: dict[str, Any] = Field(default_factory=dict)


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
    # Lock only the heat row. The query LEFT JOINs steel_grades, so a bare
    # FOR UPDATE can fail in PostgreSQL because it also attempts to lock the
    # nullable side of the outer join.
    locking = " FOR UPDATE OF h" if for_update else ""
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


@app.post("/heats/{heat_no}/materials", status_code=status.HTTP_201_CREATED)
def add_material(heat_no: str, payload: MaterialAddition) -> dict[str, Any]:
    addition_time = payload.addition_time or datetime.now(timezone.utc)
    material_code = payload.material_code.strip().upper()
    unit = payload.unit.strip()

    with db_connection() as conn:
        with conn.transaction():
            heat = fetch_heat(conn, heat_no, for_update=True)
            equipment_id = None
            equipment_code = None
            if payload.equipment_code:
                equipment = conn.execute(
                    "SELECT id, code FROM equipment WHERE code = %s AND is_active = TRUE",
                    (payload.equipment_code,),
                ).fetchone()
                if not equipment:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Equipment {payload.equipment_code} not found or inactive",
                    )
                equipment_id = equipment["id"]
                equipment_code = equipment["code"]

            attributes = {
                **payload.attributes,
                "actor": payload.actor,
                "recorded_by": "heat-management-api",
            }
            row = conn.execute(
                """
                INSERT INTO material_consumptions (
                    heat_id,
                    equipment_id,
                    material_code,
                    material_name,
                    quantity,
                    unit,
                    addition_time,
                    source_system,
                    batch_no,
                    attributes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    material_code,
                    material_name,
                    quantity::double precision AS quantity,
                    unit,
                    addition_time,
                    source_system,
                    batch_no,
                    attributes,
                    created_at
                """,
                (
                    heat["id"],
                    equipment_id,
                    material_code,
                    payload.material_name,
                    payload.quantity,
                    unit,
                    addition_time,
                    payload.source_system,
                    payload.batch_no,
                    Jsonb(attributes),
                ),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO heat_events (
                    event_type,
                    source_system,
                    source_event_id,
                    area,
                    equipment_id,
                    heat_id,
                    severity,
                    occurred_at,
                    payload
                )
                VALUES (
                    'MATERIAL_ADDED',
                    'LEVEL2_MATERIAL_TRACKING',
                    %s,
                    %s,
                    %s,
                    %s,
                    'INFO',
                    %s,
                    %s
                )
                """,
                (
                    f"MT-{heat_no}-{material_code}-{datetime.now(timezone.utc).timestamp()}",
                    heat["status"],
                    equipment_id,
                    heat["id"],
                    addition_time,
                    Jsonb(
                        {
                            "material_code": material_code,
                            "material_name": payload.material_name,
                            "quantity": payload.quantity,
                            "unit": unit,
                            "batch_no": payload.batch_no,
                            "equipment_code": equipment_code,
                            "actor": payload.actor,
                        }
                    ),
                ),
            )

    return {"heat_no": heat_no, "equipment_code": equipment_code, **row}


@app.get("/heats/{heat_no}/materials")
def list_materials(
    heat_no: str,
    material_code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    with db_connection() as conn:
        heat = fetch_heat(conn, heat_no)
        params: list[Any] = [heat["id"]]
        where_material = ""
        if material_code:
            where_material = "AND mc.material_code = %s"
            params.append(material_code.strip().upper())
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT
                mc.id,
                mc.material_code,
                mc.material_name,
                mc.quantity::double precision AS quantity,
                mc.unit,
                mc.addition_time,
                mc.source_system,
                mc.batch_no,
                e.code AS equipment_code,
                mc.attributes,
                mc.created_at
            FROM material_consumptions mc
            LEFT JOIN equipment e ON e.id = mc.equipment_id
            WHERE mc.heat_id = %s
            {where_material}
            ORDER BY mc.addition_time DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return {"heat_no": heat_no, "status": heat["status"], "items": rows}


@app.get("/heats/{heat_no}/material-summary")
def material_summary(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        heat = fetch_heat(conn, heat_no)
        rows = conn.execute(
            """
            SELECT
                material_code,
                COALESCE(MAX(material_name), material_code) AS material_name,
                unit,
                SUM(quantity)::double precision AS total_quantity,
                COUNT(*) AS additions,
                MIN(addition_time) AS first_addition,
                MAX(addition_time) AS last_addition
            FROM material_consumptions
            WHERE heat_id = %s
            GROUP BY material_code, unit
            ORDER BY material_code, unit
            """,
            (heat["id"],),
        ).fetchall()
        total_additions = conn.execute(
            "SELECT COUNT(*) AS count FROM material_consumptions WHERE heat_id = %s",
            (heat["id"],),
        ).fetchone()["count"]
    return {
        "heat_no": heat_no,
        "status": heat["status"],
        "total_additions": total_additions,
        "materials": rows,
    }
