# Level 2 System Architecture

## 1. Purpose

This document defines the initial software and integration architecture for the Steelmaking Level 2 Platform. It is intentionally designed so engineering and development can proceed before the production server and live plant network are available.

## 2. Process scope

Primary steelmaking route:

```text
Raw Materials
    │
    ▼
EAF (Electric Arc Furnace)
    │
    ▼
LF (Ladle Furnace)
    │
    ▼
CCM (Continuous Casting Machine)
    │
    ▼
Billet / Product
```

## 3. Automation hierarchy

```text
┌──────────────────────────────────────────────────────┐
│ Level 3 / MES / ERP                                  │
│ Production orders, grades, plans, reporting          │
└────────────────────────┬─────────────────────────────┘
                         │
                         │ REST / DB / Message Interface
                         ▼
┌──────────────────────────────────────────────────────┐
│ Level 2 Steelmaking Platform                         │
│                                                      │
│  Heat Management       Material Tracking             │
│  Event Management      Quality / Lab                 │
│  EAF Model             LF Model                      │
│  CCM Tracking          Historian                     │
│  KPI / Reports         Audit / Diagnostics           │
└────────────────────────┬─────────────────────────────┘
                         │
                         │ OPC UA / S7 / TCP / Vendor API
                         ▼
┌──────────────────────────────────────────────────────┐
│ Level 1 Gateway / Automation                         │
│ PLC, DCS, SCADA, drives, instrumentation             │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
                    Field Devices
```

## 4. Architectural principles

1. **Level 1 remains authoritative for equipment control and safety.** Level 2 does not directly bypass PLC interlocks.
2. **Level 2 is process-oriented.** It tracks heats, material, chemistry, process events, production status and process recommendations.
3. **All external interfaces are isolated behind adapters/gateways.** This prevents vendor-specific PLC or MES details from leaking into the business domain.
4. **Historian data and transactional production data are separated logically.** High-frequency process values use time-series storage patterns while master/transaction data use relational tables.
5. **Local-first development.** Every core service must run in containers on a developer workstation before deployment to the plant server.
6. **Traceability by design.** Every important record is associated with heat number, equipment, timestamp and source.
7. **Read-only first.** Initial plant integration should begin with read-only acquisition. Setpoint/write paths must be enabled only after FAT/SAT approval.

## 5. Logical modules

### 5.1 Heat Management
- Create/import production heat
- Track current process stage
- Track start/end timestamps
- Maintain lifecycle status
- Link EAF, LF and CCM records

### 5.2 Event & Alarm Management
- Normalize events from Level 1
- Record process milestones
- Record alarms and acknowledgements
- Preserve source timestamp and ingestion timestamp

### 5.3 Historian
- Persist timestamped process tags
- Support tag quality/status
- Support query by heat, equipment, tag and time range
- Provide data source for KPI and future process models

### 5.4 Process Interfaces
- Level 1 inbound process data/events
- Level 1 outbound approved recommendations/setpoints
- Level 3 inbound production orders and product specification
- Level 3 outbound production result, consumption and quality summaries

### 5.5 KPI & Reporting
Initial KPI candidates:
- Tap-to-Tap time
- Power-on time
- kWh/t
- Oxygen/t
- Yield
- Material consumption/t
- Casting duration
- Downtime
- Grade hit rate

## 6. Deployment topology - local development

```text
Developer Workstation
│
├── Docker Network: level2-net
│   ├── historian-db (PostgreSQL + TimescaleDB)
│   ├── future backend/API
│   ├── future Level 1 simulator
│   └── future frontend
│
└── Local documentation and tests
```

## 7. Deployment topology - future production

```text
Plant OT Network
│
├── Level 1 PLC/DCS
│      │
│      ▼
├── Level 1 Gateway / Integration Zone
│      │
│      ▼
├── Level 2 Application Server
│      ├── Backend services
│      ├── Historian DB
│      ├── UI
│      └── Reporting
│
└── Level 3 / MES integration
```

Exact network zones, firewalls, redundancy, backup, domain integration and production sizing remain client-infrastructure dependencies.

## 8. Current client dependencies

The following information is required before final plant integration:
- PLC/DCS vendor and models
- Network architecture and IP plan
- Available industrial protocols
- Actual Level 1 tag list and data types
- Tag update rates
- PLC DB/block definitions where applicable
- Level 3/MES interface specification
- Heat numbering convention
- Grade/master data
- Production sequence definitions
- Alarm/event definitions
- Server sizing and OS policy
- Cybersecurity and backup requirements

## 9. Deliverable status

This document represents the initial **System Architecture deliverable** and is expected to be refined after receipt of plant engineering documents.