# Unified Tobacco ERP Platform

Phase 1 implementation scaffold for the unified business system:

- `api/`: FastAPI + SQLAlchemy + Alembic + JWT + WebSockets
- `web/`: Next.js App Router dashboard UI
- `docker-compose.unified.yml`: local orchestration (Postgres, Redis, API, worker, web)

## Quick start

```bash
cd unified_platform
docker compose -f docker-compose.unified.yml up --build
```

Services:

- API: `http://localhost:8080`
- API docs: `http://localhost:8080/docs`
- Web: `http://localhost:3000`
- Postgres: `localhost:5434`
- Redis: `localhost:6379`

## Phase 1 scope implemented

- Database schema for core identity, PIM, suppliers, purchasing, inbound receiving, inventory, valuation, audit, and outbox events.
- REST API namespace under `/api/v1/*`.
- WebSocket channels:
  - `/api/v1/ws/dashboard`
  - `/api/v1/ws/inventory/{location_id}`
  - `/api/v1/ws/receiving/{shipment_id}`
- Minimal Scandinavian-style dashboard and key module pages in Next.js.

## Notes

- This is a production-oriented foundation, not a full 5-phase completion in one commit.
- Phase 2-5 are prepared by contract shape (events, integration tables, route layout), but detailed logic is still to be expanded.
- For Coolify Docker Compose deployments, use:
  - Base Directory: `unified_platform`
  - Docker Compose Location: `docker-compose.unified.yml`
