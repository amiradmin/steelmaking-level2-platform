# Signed License and Read-only Mode

The Steelmaking Level 2 platform supports a transparent signed offline license. It is intentionally non-destructive: license expiry never deletes historian data, heat records, users, or configuration.

## Runtime states

- `ACTIVE`: full monitoring and write access.
- `GRACE`: full access continues, but the UI shows a renewal warning.
- `READ_ONLY`: login, dashboards, historian reads, Production Flow, System Map, and API `GET` requests remain available. Mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) return HTTP `423` with code `LICENSE_READ_ONLY`.
- `INVALID`: a modified or incorrectly signed token is treated as read-only.
- `DEVELOPMENT`: license enforcement is disabled for a local development environment.

The same signed token is checked by both the Django Level 2 API and the FastAPI Heat Management service.

## Development default

`.env.example` keeps local development unlocked:

```env
LICENSE_ALLOW_UNLICENSED=1
LICENSE_TOKEN=
```

This avoids accidentally locking a developer workstation.

## Enable licensing for a customer deployment

Keep the vendor private key outside Git, outside the customer server, and in a secure backup. The repository contains only the matching public key.

Issue a license token from a trusted machine:

```bash
uv run --with cryptography scripts/issue_license.py \
  --private-key ~/.steelmaking-level2-license-private.pem \
  --customer "Mianeh Steel Complex" \
  --license-id "MIA-2026-001" \
  --expires-at "2026-10-13T23:59:59+03:30" \
  --grace-days 7
```

The command prints one line beginning with `LICENSE_TOKEN=`. Copy that complete line into the deployment `.env` and set:

```env
LICENSE_ALLOW_UNLICENSED=0
LICENSE_TOKEN=<signed token printed by issue_license.py>
```

Then recreate the application services:

```bash
docker compose up -d --build level2-api heat-management frontend nginx
```

## Check current license state

```bash
curl -s http://127.0.0.1/api/v1/license
```

The frontend also displays a small license indicator. `GRACE`, `READ_ONLY`, and `INVALID` are clearly visible to the operator.

## Renewal

Renewal does not require database migration or data changes. Issue a new signed token with a later `expires_at`, replace `LICENSE_TOKEN` in `.env`, then restart the API services:

```bash
docker compose up -d --force-recreate level2-api heat-management
```

## Security model

The token payload contains the customer, license id, expiry and grace period. It is signed with Ed25519. Editing the expiry date or customer name invalidates the signature and switches the system to read-only mode.

The private signing key must never be committed to this repository or copied to the customer server. A customer with full source-code and root access can always modify software checks, so licensing should complement—not replace—contractual payment milestones and controlled production deployment.
