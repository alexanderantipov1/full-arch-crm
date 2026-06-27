# Incidents

- 2026-06-08T20:47:44Z — Full `make test` with default shell `python` failed
  because dependencies such as `structlog`, `respx`, `agents`, `chevron`, and
  `arq` are not installed in that interpreter.
- 2026-06-08T20:47:44Z — Full `.venv` suite failed 3 unrelated Project Manager
  dashboard tests in `tests/api/test_dashboard_pm.py`. Mission-focused Agent
  Runtime tests passed.
