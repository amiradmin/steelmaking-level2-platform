# Heat Event & Alarm Model

## 1. Purpose

The Event Model provides a common vocabulary for Level 1 signals, Level 2 business logic and Level 3 reporting. Raw PLC bits may differ by vendor; Level 2 normalizes them into stable event types.

## 2. Event envelope

Every normalized event should contain:

```json
{
  "event_id": "uuid",
  "event_type": "POWER_ON",
  "source_system": "LEVEL1",
  "source_event_id": "optional-vendor-id",
  "area": "EAF",
  "equipment_code": "EAF-01",
  "heat_no": "H260001",
  "occurred_at": "2026-09-06T10:00:00Z",
  "ingested_at": "2026-09-06T10:00:00.120Z",
  "severity": "INFO",
  "payload": {}
}
```

## 3. Heat lifecycle events

### Planning / creation
- `HEAT_PLANNED`
- `HEAT_CREATED`
- `HEAT_CANCELLED`

### Charging
- `CHARGE_START`
- `CHARGE_BATCH_START`
- `CHARGE_BATCH_END`
- `CHARGE_END`

### EAF
- `EAF_START`
- `POWER_ON`
- `POWER_OFF`
- `OXYGEN_START`
- `OXYGEN_STOP`
- `CARBON_INJECTION_START`
- `CARBON_INJECTION_STOP`
- `EAF_SAMPLE_TAKEN`
- `EAF_TEMPERATURE_TAKEN`
- `EAF_READY_TO_TAP`

### Tapping
- `TAPPING_START`
- `TAPPING_END`
- `LADLE_RECEIVED`

### LF
- `LF_START`
- `LF_POWER_ON`
- `LF_POWER_OFF`
- `ARGON_START`
- `ARGON_STOP`
- `ALLOY_ADDITION`
- `LF_SAMPLE_TAKEN`
- `LF_TEMPERATURE_TAKEN`
- `LF_READY`
- `LF_END`

### CCM
- `LADLE_OPEN`
- `CAST_START`
- `STRAND_START`
- `STRAND_STOP`
- `LADLE_CLOSE`
- `CAST_END`

### Completion
- `HEAT_COMPLETED`
- `HEAT_ABORTED`

## 4. Stage transition proposal

```text
PLANNED
  │ HEAT_CREATED
  ▼
CREATED
  │ CHARGE_START
  ▼
CHARGING
  │ EAF_START / POWER_ON
  ▼
EAF
  │ TAPPING_START
  ▼
TAPPING
  │ LF_START
  ▼
LF
  │ CAST_START
  ▼
CASTING
  │ CAST_END
  ▼
COMPLETED
```

Exceptions can move a heat to `HOLD`, `ABORTED` or `CANCELLED` according to approved business rules.

## 5. Event idempotency

Where the source provides an event identifier, Level 2 should enforce uniqueness using:

```text
(source_system, source_event_id)
```

Where no source event identifier exists, the adapter should generate a deterministic deduplication key using source, event type, equipment and source timestamp where technically safe.

## 6. Event ordering

Level 2 stores both source and ingestion time because events may arrive late or out of order. Domain logic must prefer `occurred_at` for process sequence while still preserving ingestion order for diagnostics.

## 7. Alarm model

### Severity

```text
INFO
WARNING
HIGH
CRITICAL
```

### State

```text
ACTIVE_UNACKNOWLEDGED
ACTIVE_ACKNOWLEDGED
CLEARED_UNACKNOWLEDGED
CLEARED_ACKNOWLEDGED
```

### Alarm envelope

```json
{
  "alarm_code": "EAF-COOLING-001",
  "source_system": "LEVEL1",
  "equipment_code": "EAF-01",
  "heat_no": "H260001",
  "severity": "HIGH",
  "state": "ACTIVE_UNACKNOWLEDGED",
  "message": "Cooling water flow low",
  "active_at": "2026-09-06T10:11:20Z",
  "cleared_at": null,
  "acknowledged_at": null
}
```

## 8. Business-event vs raw-signal rule

A raw PLC bit is not automatically a business event. Adapters may combine/debounce signals before producing normalized Level 2 events. Example:

```text
PLC_POWER_CONTACTOR = 1
+ valid EAF heat context
+ stable for configured debounce interval
→ POWER_ON
```

## 9. Audit requirements

The following must be traceable:
- Source of each event/alarm
- Original source timestamp
- Adapter ingestion timestamp
- Heat association method
- Manual corrections
- Alarm acknowledgement user/time
- Any future Level 2 write/setpoint action

## 10. Open items for plant engineering

- Actual PLC event/tag mapping
- Debounce rules
- Official alarm severity mapping
- Heat context ownership
- Sequence edge cases
- Manual/maintenance operating modes
- Downtime classification hierarchy
