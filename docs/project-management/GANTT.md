# Steelmaking Level 2 — Gantt Plan

> Baseline schedule only. No task below is marked as completed.

```mermaid
gantt
    title Steelmaking Level 2 Platform — Baseline Project Plan
    dateFormat  YYYY-MM-DD
    axisFormat  %d %b

    section M1 Engineering Baseline
    Requirements and scope baseline          :m1a, 2026-09-29, 7d
    Architecture and interface baseline      :m1b, after m1a, 6d
    Environments and configuration baseline  :m1c, 2026-10-05, 7d

    section M2 Level 1 / PLC Integration
    EAF connectivity and tag map             :m2a, 2026-10-19, 10d
    LF connectivity and tag map              :m2b, 2026-10-26, 10d
    CCM connectivity and tag map             :m2c, 2026-11-02, 10d
    Data quality and reconnection tests       :m2d, 2026-11-09, 7d

    section M3 Functional Level 2
    Historian production hardening            :m3a, 2026-11-16, 12d
    Heat management workflow                  :m3b, 2026-11-16, 14d
    Alarm and event workflows                 :m3c, 2026-11-23, 12d
    Operator dashboards and reports           :m3d, 2026-11-30, 14d
    KPI validation                            :m3e, 2026-12-07, 7d

    section M4 Production Hardening
    Authentication and RBAC                   :m4a, 2026-12-14, 8d
    Audit and cybersecurity hardening         :m4b, 2026-12-21, 8d
    Monitoring logging and alerting           :m4c, 2026-12-14, 10d
    Backup restore and DR rehearsal           :m4d, 2026-12-28, 7d
    Performance and resilience testing        :m4e, 2027-01-04, 7d

    section M5 FAT SAT Commissioning
    FAT test campaign                         :m5a, 2027-01-11, 8d
    Site installation readiness               :m5b, 2027-01-18, 7d
    SAT with real plant interfaces            :m5c, 2027-01-25, 8d
    Operator/admin training                    :m5d, 2027-01-25, 6d
    Go-live readiness review                  :milestone, m5e, 2027-02-05, 1d
```

## Scheduling rules

- Dates are planning targets, not completion claims.
- Dependencies should be updated when plant interface information becomes available.
- Any scope change affecting a milestone target should be logged in the decision/change register.
