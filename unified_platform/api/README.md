# Unified ERP API

## Run locally

```bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

## Default seed user

- Email: `admin@unified.local`
- Password: `admin123`

## Implemented API groups

- `/api/v1/auth/*`
- `/api/v1/rbac/*`
- `/api/v1/products*`
- `/api/v1/suppliers`
- `/api/v1/purchase-orders*`
- `/api/v1/inbound-shipments*`
- `/api/v1/inventory/*`
- `/api/v1/dashboard/kpis`
- `/api/v1/integration/sync-status`
- `/api/v1/audit/events`
