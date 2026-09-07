from __future__ import annotations

from typing import Any, Iterable

from django.db import connection


def _dictfetchall(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _dictfetchone(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row, strict=True))


def fetch_all(sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, list(params or []))
        return _dictfetchall(cursor)


def fetch_one(sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(sql, list(params or []))
        return _dictfetchone(cursor)


def ping_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def heat_by_no(heat_no: str) -> dict[str, Any] | None:
    return fetch_one(
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
        [heat_no],
    )


def heats(*, status: str | None, limit: int) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE h.status::text = %s"
        params.append(status.upper())
    params.append(limit)

    return fetch_all(
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
    )


def heat_live_values(heat_id: int) -> list[dict[str, Any]]:
    return fetch_all(
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
        [heat_id],
    )


def heat_material_summary(heat_id: int) -> list[dict[str, Any]]:
    return fetch_all(
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
        [heat_id],
    )


def heat_recent_events(heat_id: int) -> list[dict[str, Any]]:
    return fetch_all(
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
        [heat_id],
    )


def heat_active_alarms(heat_id: int) -> list[dict[str, Any]]:
    return fetch_all(
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
        [heat_id],
    )


def equipment(*, area: str | None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = "WHERE is_active = TRUE"
    if area:
        where += " AND area = %s"
        params.append(area.upper())

    return fetch_all(
        f"""
        SELECT code, name, area, equipment_type, metadata
        FROM equipment
        {where}
        ORDER BY area, code
        """,
        params,
    )


def steel_grades(*, active_only: bool) -> list[dict[str, Any]]:
    where = "WHERE is_active = TRUE" if active_only else ""
    return fetch_all(
        f"""
        SELECT code, name, revision, specification, is_active
        FROM steel_grades
        {where}
        ORDER BY code, revision DESC
        """
    )


def events(
    *,
    heat_no: str | None,
    event_type: str | None,
    source_system: str | None,
    limit: int,
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

    return fetch_all(
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
    )


def alarms(
    *,
    state: str | None,
    severity: str | None,
    heat_no: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if state:
        conditions.append("a.state::text = %s")
        params.append(state.upper())
    if severity:
        conditions.append("a.severity::text = %s")
        params.append(severity.upper())
    if heat_no:
        conditions.append("h.heat_no = %s")
        params.append(heat_no)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    return fetch_all(
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
    )


def historian_latest(
    *,
    area: str | None,
    equipment_code: str | None,
    quality: str | None,
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

    return fetch_all(
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
    )


def historian_tag(tag_name: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT tag_name, engineering_unit, data_type, sampling_mode, expected_period_ms
        FROM process_tags
        WHERE tag_name = %s AND is_active = TRUE
        """,
        [tag_name],
    )


def historian_tag_samples(
    *,
    tag_name: str,
    start: Any | None,
    end: Any | None,
    heat_no: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    conditions = ["pt.tag_name = %s"]
    params: list[Any] = [tag_name]

    if start is not None:
        conditions.append("ps.ts >= %s")
        params.append(start)
    if end is not None:
        conditions.append("ps.ts <= %s")
        params.append(end)
    if heat_no:
        conditions.append("h.heat_no = %s")
        params.append(heat_no)

    params.append(limit)
    where = " AND ".join(conditions)

    return fetch_all(
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
    )
