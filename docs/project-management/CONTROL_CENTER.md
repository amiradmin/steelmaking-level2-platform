# Project Control Center

This page is the project-management entry point for the Steelmaking Level 2 Platform.

## Core planning artifacts

- [Roadmap](ROADMAP.md)
- [Gantt](GANTT.md)
- [RAID register](RAID.md)
- [Governance](GOVERNANCE.md)

## Milestone trackers

- #15 — M1 Engineering Baseline
- #16 — M2 Level 1 / PLC Integration
- #17 — M3 Functional Level 2
- #18 — M4 Production Hardening
- #19 — M5 FAT / SAT / Commissioning

## Epics

- #20 — Platform architecture and engineering baseline
- #21 — Level 1 / PLC / OPC UA integration
- #22 — Historian and industrial data management
- #23 — Heat management and process orchestration
- #24 — Event and alarm management
- #25 — Operator UI, dashboards and reporting
- #26 — Authentication, authorization and cybersecurity
- #27 — MES / Level 3 integration
- #28 — DevOps, deployment and observability
- #29 — Quality assurance, FAT/SAT and commissioning

## Initial task backlog

Issues #30 through #61 form the initial planned backlog. Every task is linked to a parent Epic and a planned milestone tracker.

## Control rules

1. Nothing starts as Done.
2. Existing source code does not automatically mean an issue is complete.
3. Completion requires explicit review against acceptance criteria.
4. Scope changes use `[CHANGE]` issues.
5. Defects use `[BUG]` issues.
6. Significant architecture/interface decisions should be documented as ADRs.
7. Milestone completion is explicitly approved; it is never inferred.

## Suggested board columns

`Planned → Ready → In Progress → Review → Done`

Optional: `Blocked`.

## Weekly project-control review

- blocked and aging issues;
- external plant dependencies;
- milestone drift;
- new or changed RAID items;
- PLC/tag-map readiness;
- FAT/SAT readiness;
- defects and regressions;
- security and deployment readiness;
- decisions requiring customer/plant approval.
