# Release notes — 1.0.5

## Stable-line scope

No business-domain features and no new migrations. This maintenance release hardens the Docker release-validation gate.

## Fixed

- Release validation now uses a dedicated Compose project (`mrp_release_<version>` by default), preventing cleanup from stopping the normal development stack.
- Validation uses ephemeral host ports by default, preventing collisions with already-running PostgreSQL/web services.
- Isolated validation volumes are deleted by default after the run, so each release gate starts from a clean PostgreSQL/Redis state.
- `RELEASE_KEEP_STACK=1` still preserves the complete stack for diagnosis.
- `RELEASE_KEEP_VOLUMES=1` preserves only the isolated named volumes when normal cleanup is used.
- Docker Compose host ports are now parameterized with `POSTGRES_HOST_PORT` and `WEB_HOST_PORT`.
- Static compose lint verifies that the host-port parameters remain present.

## Validation target

Run:

```bash
./scripts/preflight.sh
./scripts/release_validate.sh
```

The integrated gate still requires a Docker-capable host.
