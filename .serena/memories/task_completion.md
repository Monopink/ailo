- After coding tasks, re-read relevant docs/specs to verify implementation still matches prototypes.
backend/app`; ensure FastAPI container starts cleanly via `docker compose -f deployment/docker-compose.yml up backend`.
- Check logs in `backend/app/logs` (mounted to `/logs` in compose) for startup/runtime errors, especially background workers (buffer scanner, contact-request worker).
- Confirm DB migrations (Alembic) applied if schema changes occur; update `backend/database/init` scripts if base data changes.
- Document any deviations or uncertainties back to the user, especially when specs are ambiguous—do not silently introduce assumptions.
