# Level 1 / Level 2 / Level 3 Interface Architecture

## 1. Objective

Define stable interface boundaries before plant connectivity is available. Vendor-specific details are isolated behind adapters so Level 2 domain services do not depend directly on PLC or MES implementation details.

## 2. Level 1 → Level 2 data classes

### Continuous process values
Examples:
- Electrical power, voltage and current
- Electrode position
- Oxygen and carbon flow
- Material weights
- Steel/ladle/tundish temperature
- Casting speed
- Cooling values
- Equipment status

Required metadata per sample:

```text
source_system
area
unit
 tag_name
value
value_type
engineering_unit
source_timestamp
ingestion_timestamp
quality
heat_no (when resolved)
```

### Discrete events
Examples:

```text
HEAT_CREATED
CHARGE_START
CHARGE_END
POWER_ON
POWER_OFF
SAMPLE_TAKEN
TAPPING_START
TAPPING_END
LF_START
LF_END
CAST_START
CAST_END
HEAT_COMPLETED
```

### Alarms
Each alarm should include:

```text
alarm_code
source
severity
state
message
active_timestamp
clear_timestamp
ack_timestamp
heat_no
```

## 3. Level 2 → Level 1 interface

Initial integration mode: **read-only**.

Future approved write classes may include:
- Recipe/setpoint download
- Process model recommendation
- Target temperature
- Material addition recommendation
- Heat/grade context

Rules:
1. Writes must be explicit and auditable.
2. Every write must include correlation ID, timestamp, target, value and result.
3. PLC safety logic and interlocks always remain authoritative.
4. Write capability is disabled by configuration until SAT authorization.

## 4. Level 3 → Level 2 interface

Candidate inbound entities:
- Production order
- Heat plan
- Steel grade
- Product/billet specification
- Planned quantity
- Due date / sequence
- Master data

Example normalized contract:

```json
{
  "order_id": "PO-2026-001",
  "heat_no": "H260001",
  "grade_code": "ST37",
  "planned_weight_t": 80.0,
  "billet_section": "150x150",
  "planned_sequence": 1
}
```

## 5. Level 2 → Level 3 interface

Candidate outbound entities:
- Heat production result
- Actual start/end times
- Actual production weight
- Material consumption summary
- Energy summary
- Chemistry/quality status
- Billet genealogy
- Exception/downtime summary

## 6. Protocol abstraction

```text
                       ┌────────────────────┐
PLC/DCS ──────────────►│ Level1Adapter      │
                       └─────────┬──────────┘
                                 │ normalized messages
                                 ▼
                        Level 2 Domain
                                 ▲
                                 │ normalized messages
                       ┌─────────┴──────────┐
MES/ERP ──────────────►│ Level3Adapter      │
                       └────────────────────┘
```

Candidate Level 1 transports:
- OPC UA
- Siemens S7
- TCP/IP vendor protocol
- Database exchange

Candidate Level 3 transports:
- REST API
- Message broker
- Database views/stored procedures
- File exchange where unavoidable

Final protocol selection is pending client interface documentation.

## 7. Reliability requirements

All interfaces should implement:
- Connection health state
- Retry with backoff
- Timeout policy
- Idempotency where applicable
- Source timestamp preservation
- Store-and-forward for transient outages where required
- Dead-letter/error recording
- Audit trail

## 8. Data quality states

Proposed normalized quality values:

```text
GOOD
UNCERTAIN
BAD
STALE
UNKNOWN
```

BAD/STALE process values must not be used for automatic process recommendations without an explicit fallback policy.

## 9. Time synchronization

Production deployment requires reliable time synchronization across PLC, Level 2 and Level 3 systems. Level 2 stores both `source_timestamp` and `ingestion_timestamp` to detect transport delay and clock anomalies.

## 10. Open items for client

- Final protocol(s)
- PLC endpoint details
- Namespace/DB definitions
- Actual tag list
- Sampling/change-of-value policy
- MES endpoints/schema
- Authentication method
- Firewall ports
- Network redundancy requirements
- Ownership of heat number creation
- Expected acknowledgement semantics
