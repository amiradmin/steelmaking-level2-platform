# RAID Register

RAID = Risks, Assumptions, Issues, Dependencies.

## Risks

| ID | Risk | Probability | Impact | Response | Status |
|---|---|---:|---:|---|---|
| R-01 | Real PLC tag/address maps arrive late or are incomplete | High | High | Keep simulation separate; require reviewed mapping before real mode | Open |
| R-02 | PLC/network access differs from lab assumptions | Medium | High | Connectivity survey and packet-level validation | Open |
| R-03 | Historian write volume exceeds initial sizing | Medium | High | Capacity test, retention/compression policy, index review | Open |
| R-04 | Undefined Level 3/MES interface contract | High | High | Freeze interface contract before integration build | Open |
| R-05 | Production authentication requirements arrive late | Medium | High | Define IAM/RBAC/security baseline before commissioning | Open |
| R-06 | Time synchronization across PLC/servers is inconsistent | Medium | High | Define NTP/PTP and timestamp ownership policy | Open |
| R-07 | Alarm limits and priorities are not formally approved | Medium | Medium | Alarm rationalization workshop and signed matrix | Open |
| R-08 | Single-node deployment becomes a production SPOF | Medium | High | Define recovery, backup and HA target architecture | Open |

## Assumptions

| ID | Assumption | Validation needed | Status |
|---|---|---|---|
| A-01 | EAF, LF and CCM expose stable industrial interfaces | Interface survey | Open |
| A-02 | Plant provides server/network/security prerequisites | Infrastructure checklist | Open |
| A-03 | Heat identifier can be correlated across EAF → LF → CCM | Process/data workshop | Open |
| A-04 | Time-series retention requirements can be agreed before production sizing | Data retention workshop | Open |

## Dependencies

| ID | Dependency | Owner | Needed by | Status |
|---|---|---|---|---|
| D-01 | Approved PLC tag maps for EAF/LF/CCM | Plant automation team | M2 | Open |
| D-02 | Network addressing/VLAN/firewall information | Plant IT/OT | M2 | Open |
| D-03 | MES/ERP interface specification | Plant Level 3 team | M3/M4 | Open |
| D-04 | Alarm and KPI definitions | Process/operations | M3 | Open |
| D-05 | Production server specification | IT | M4 | Open |

## Issue policy

Operational problems discovered during implementation are tracked as GitHub Issues and linked back here when they materially affect scope, schedule or risk.