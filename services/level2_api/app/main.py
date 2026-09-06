from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Connection
from psycopg.rows import dict_row

DB_HOST = os.getenv("DB_HOST", "historian-db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")
CORS_ORIGINS = [
    value.strip()
    for value in os.getenv("API_CORS_ORIGINS", "*").split(",")
    if value.strip()
]

app = FastAPI(
    title="Steelmaking Level 2 API",
    version="0.1.0",
    description=(
        "Versioned public API for Level 2 dashboard and integration consumers. "
        "Heat Management remains the domain write service; this API exposes a stable read contract."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


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


def fetch_heat_by_no(conn: Connection, heat_no: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            h.id,
            h.heat_no,
            h.status::text AS status,
            sg.code AS grade_code,
            sg.revision AS grade_revision,
            sg.name AS grade_name,
            h.planned_weight_t,
            h.actual_weight_t,
            h.production_order_id,
            h.planned_sequence,
            h.attributes,
            h.created_at,
            h.started_at,
            h.completed_at,
            h.updated_at
        FROM heats h
        LEFT JOIN steel_grades sg ON sg.id = h.grade_id
        WHERE h.heat_no = %s
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
        return {
            "status": "ok",
            "database": "reachable",
            "service": "level2-api",
            "api_version": "v1",
        }
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/api/v1/meta")
def api_meta() -> dict[str, Any]:
    return {
        "name": "Steelmaking Level 2 API",
        "version": "0.1.0",
        "api_version": "v1",
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


@app.get("/api/v1/heats")
def list_heats(
    heat_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if heat_status:
        where = "WHERE h.status::text = %s"
        params.append(heat_status.upper())
    params.append(limit)

    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t,
                h.actual_weight_t,
                h.production_order_id,
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


@app.get("/api/v1/heats/{heat_no}")
def get_heat(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        return fetch_heat_by_no(conn, heat_no)


@app.get("/api/v1/heats/{heat_no}/overview")
def heat_overview(heat_no: str) -> dict[str, Any]:
    with db_connection() as conn:
        heat = fetch_heat_by_no(conn, heat_no)
        heat_id = heat["id"]

        live_values = conn.execute(
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
            (heat_id,),
        ).fetchall()

        material_summary = conn.execute(
            """
            SELECT
                material_code,
                COALESCE(MAX(material_name), material_code) AS material_name,
                unit,
                SUM(quantity)::double precision AS total_quantity,
                COUNT(*) AS additions
            FROM material_consumptions
            WHERE heat_id = %s
            GROUP BY material_code, unit
            ORDER BY material_code, unit
            """,
            (heat_id,),
        ).fetchall()

        recent_events = conn.execute(
            """
            SELECT
                event_type,
                source_system,
                area,
                severity,
                occurred_at,
                payload
            FROM heat_events
            WHERE heat_id = %s
            ORDER BY occurred_at DESC
            LIMIT 20
            """,
            (heat_id,),
        ).fetchall()

        active_alarms = conn.execute(
            """
            SELECT
                alarm_code,
                severity::text AS severity,
                state::text AS state,
                message,
                active_at,
                cleared_at
            FROM alarms
            WHERE heat_id = %s
              AND state IN ('ACTIVE_UNACKNOWLEDGED', 'ACTIVE_ACKNOWLEDGED')
            ORDER BY active_at DESC
            """,
            (heat_id,),
        ).fetchall()

    return {
        "heat": heat,
        "live_values": live_values,
        "material_summary": material_summary,
        "recent_events": recent_events,
        "active_alarms": active_alarms,
    }


@app.get("/api/v1/equipment")
def equipment(area: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = "WHERE is_active = TRUE"
    if area:
        where += " AND area = %s"
        params.append(area.upper())

    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT code, name, area, equipment_type, metadata
            FROM equipment
            {where}
            ORDER BY area, code
            """,
            params,
        ).fetchall()


@app.get("/api/v1/steel-grades")
def steel_grades(active_only: bool = True) -> list[dict[str, Any]]:
    where = "WHERE is_active = TRUE" if active_only else ""
    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT code, name, revision, specification, is_active
            FROM steel_grades
            {where}
            ORDER BY code, revision DESC
            """
        ).fetchall()


@app.get("/api/v1/events")
def events(
    heat_no: str | None = None,
    event_type: str | None = None,
    source_system: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if heat_no:
        conditions.append("h.heat_no = %s")
        params.append(heat_no)
    if event_type:
        conditions.append("he.event_type = %s")
        params.append(event_type.upper())
    if source_system:
        conditions.append("he.source_system = %s")
        params.append(source_system)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                he.event_type,
                he.source_system,
                he.source_event_id,
                he.area,
                e.code AS equipment_code,
                h.heat_no,
                he.severity,
                he.occurred_at,
                he.payload
            FROM heat_events he
            LEFT JOIN heats h ON h.id = he.heat_id
            LEFT JOIN equipment e ON e.id = he.equipment_id
            {where}
            ORDER BY he.occurred_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()


@app.get("/api/v1/alarms")
def alarms(
    alarm_state: str | None = Query(default=None, alias="state"),
    severity: str | None = None,
    heat_no: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if alarm_state:
        conditions.append("a.state::text = %s")
        params.append(alarm_state.upper())
    if severity:
        conditions.append("a.severity::text = %s")
        params.append(severity.upper())
    if heat_no:
        conditions.append("h.heat_no = %s")
        params.append(heat_no)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                a.alarm_code,
                a.source_system,
                e.code AS equipment_code,
                h.heat_no,
                a.severity::text AS severity,
                a.state::text AS state,
                a.message,
                a.active_at,
                a.cleared_at,
                a.acknowledged_at,
                a.acknowledged_by,
                a.payload
            FROM alarms a
            LEFT JOIN heats h ON h.id = a.heat_id
            LEFT JOIN equipment e ON e.id = a.equipment_id
            {where}
            ORDER BY a.active_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()


@app.get("/api/v1/historian/latest")
def historian_latest(
    area: str | None = None,
    equipment_code: str | None = None,
    quality: str | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = ["pt.is_active = TRUE"]
    params: list[Any] = []

    if area:
        conditions.append("e.area = %s")
        params.append(area.upper())
    if equipment_code:
        conditions.append("e.code = %s")
        params.append(equipment_code)
    if quality:
        conditions.append("lpv.quality::text = %s")
        params.append(quality.upper())

    where = " AND ".join(conditions)

    with db_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                lpv.tag_name,
                e.code AS equipment_code,
                e.area,
                lpv.engineering_unit,
                lpv.value_double,
                lpv.value_text,
                lpv.quality::text AS quality,
                lpv.ts,
                h.heat_no
            FROM latest_process_values lpv
            JOIN process_tags pt ON pt.id = lpv.tag_id
            LEFT JOIN equipment e ON e.id = pt.equipment_id
            LEFT JOIN heats h ON h.id = lpv.heat_id
            WHERE {where}
            ORDER BY e.area, lpv.tag_name
            """,
            params,
        ).fetchall()


@app.get("/api/v1/historian/tags/{tag_name}/samples")
def historian_tag_samples(
    tag_name: str,
    start: datetime | None = None,
    end: datetime | None = None,
    heat_no: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    conditions = ["pt.tag_name = %s"]
    params: list[Any] = [tag_name]

    if start:
        conditions.append("ps.ts >= %s")
        params.append(start)
    if end:
        conditions.append("ps.ts <= %s")
        params.append(end)
    if heat_no:
        conditions.append("h.heat_no = %s")
        params.append(heat_no)

    params.append(limit)
    where = " AND ".join(conditions)

    with db_connection() as conn:
        tag = conn.execute(
            """
            SELECT tag_name, engineering_unit, data_type, sampling_mode, expected_period_ms
            FROM process_tags
            WHERE tag_name = %s AND is_active = TRUE
            """,
            (tag_name,),
        ).fetchone()
        if not tag:
            raise HTTPException(status_code=404, detail=f"Tag {tag_name} not found")

        rows = conn.execute(
            f"""
            SELECT
                ps.ts,
                ps.value_double,
                ps.value_text,
                ps.quality::text AS quality,
                h.heat_no
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            LEFT JOIN heats h ON h.id = ps.heat_id
            WHERE {where}
            ORDER BY ps.ts DESC
            LIMIT %s
            """,
            params,
        ).fetchall()

    return {"tag": tag, "samples": rows}
