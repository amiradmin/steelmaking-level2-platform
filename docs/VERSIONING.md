# Project Versioning

The Steelmaking Level 2 Platform uses Semantic Versioning (`MAJOR.MINOR.PATCH`).

- **MAJOR**: incompatible changes to APIs, data contracts, deployment configuration, or core workflows.
- **MINOR**: backward-compatible functionality, modules, integrations, or substantial operator-facing capabilities.
- **PATCH**: backward-compatible bug fixes, security fixes, and small refinements.

## Release procedure

1. Update `frontend/src/version.ts` with the release version.
2. Keep `frontend/package.json`'s `version` field aligned with the same version.
3. Add a dated entry to the root `CHANGELOG.md`, moving completed items out of `[Unreleased]`.
4. Run the frontend build and the relevant backend/integration tests.
5. Commit the release changes and create an annotated Git tag named `vMAJOR.MINOR.PATCH` (for example, `v0.1.0`).
6. Publish a GitHub Release using the matching changelog entry.

Do not use a release tag for ordinary development commits. Tags identify reviewed release snapshots; the changelog records the user-visible changes between them.

## Current baseline

The initial formal project baseline is `0.1.0`. The application displays the frontend version from `frontend/src/version.ts`; keep it synchronized with `frontend/package.json` and the release tag.
