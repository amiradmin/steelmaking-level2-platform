# Project Governance

## Control model

Every unit of work must be traceable to an Epic and a milestone window.

### Issue states

All newly created work starts **Open / Planned**.

Recommended workflow:
1. Planned
2. Ready
3. In Progress
4. Review
5. Done

Optional exception state: Blocked.

### Definition of Ready

An issue is Ready when:
- objective is clear;
- acceptance criteria are testable;
- dependencies are identified;
- production-vs-simulation boundary is explicit;
- required plant input is available or deliberately mocked.

### Definition of Done

An issue may only be marked Done after:
- implementation is merged;
- automated or documented verification exists;
- acceptance criteria are satisfied;
- documentation/configuration is updated;
- no unresolved critical regression is known;
- owner explicitly approves closure.

## Change control

Material changes in scope, architecture, industrial interfaces, schedule, security requirements or acceptance criteria should be recorded as a GitHub Issue using the prefix `[CHANGE]`.

## Decision log

Architectural and plant-interface decisions should be recorded using `[ADR]` issues or files under `docs/adr/`.

## Weekly review

Review:
- milestone movement;
- blocked items and external dependencies;
- new/changed risks;
- issue aging;
- defects;
- FAT/SAT readiness;
- decisions required from plant stakeholders.

## Completion rule

Do not infer completion from existing code. Project-management status is changed only when explicitly reviewed and approved.