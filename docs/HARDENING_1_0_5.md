# MRP 1.0.5 — Isolated release-validation stack

## Purpose

Release validation must never silently reuse the regular development/production Compose project. Version 1.0.5 isolates the validation stack with its own Compose project, network and named volumes.

## Isolation

`scripts/release_validate.sh` exports a project name such as `mrp_release_1_0_5` before invoking Compose. This prevents `docker compose down` from stopping an unrelated stack started from the same repository.

The gate also sets `POSTGRES_HOST_PORT=0` and `WEB_HOST_PORT=0`. All readiness checks run inside the containers, so fixed host ports are unnecessary during validation; Docker may allocate ephemeral host ports instead.

## Clean database guarantee

On successful or failed validation, the default cleanup is:

```bash
docker compose down --remove-orphans --volumes
```

This removes the isolated validation volumes, ensuring the next run does not accidentally pass because of data left by a previous validation.

For diagnosis:

```bash
RELEASE_KEEP_STACK=1 ./scripts/release_validate.sh
```

To remove containers but retain the isolated volumes:

```bash
RELEASE_KEEP_VOLUMES=1 ./scripts/release_validate.sh
```

Custom project/ports are available only when needed:

```bash
RELEASE_COMPOSE_PROJECT=my_validation \
RELEASE_POSTGRES_HOST_PORT=55432 \
RELEASE_WEB_HOST_PORT=58000 \
./scripts/release_validate.sh
```

## Development behavior

Normal `docker compose up` remains compatible: absent overrides, the compose defaults remain PostgreSQL `5432` and web `8000`.
