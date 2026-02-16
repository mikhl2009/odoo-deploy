# Docker och Deployment Troubleshooting

## Bcrypt Password Längd & Version Incompatibility Problem

### Problem
Om du ser följande fel under startup:
```
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```

Eller:
```
(trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
```

### Root Cause
**Detta är en bcrypt version incompatibility issue**, INTE ett problem med användar-lösenord!

1. **Bcrypt Initialization Bug**: Passlib 1.7.4 försöker detectera bcrypt-versionen via `__about__.__version__` vilket inte finns i nyare bcrypt versioner
2. **Bug Detection Test**: Under init körs `detect_wrap_bug()` som testar bcrypt med test-data, vilket kan trigga 72-byte felet
3. **Långa miljövariabler**: Om `POSTGRES_PASSWORD` är >72 tecken, kan det också orsaka problem

### Lösning

#### 1. Fixa Dependencies (VIKTIGAST)
I [pyproject.toml](./api/pyproject.toml), lägg till explicit bcrypt version:
```toml
dependencies = [
  "bcrypt==4.1.2",          # Lägg till denna rad FÖRE passlib
  "passlib[bcrypt]==1.7.4",
  ...
]
```

#### 2. Håll Lösenord Under 50 Tecken
Exempel i `.env`:
```bash
# ✅ BRA - 32 tecken
POSTGRES_PASSWORD=v3ZDFK7JSyko3UWd8JNPCb6sWWbefN

# ❌ DÅLIGT - 64 tecken
POSTGRES_PASSWORD=v3ZDFK7JSyko3UWd8JNPCb6sWWbefN0fX5tnjNwJe1DdqaXe005S6feZFIduyRH2
```

### Coolify-specifikt
När du deployar till Coolify:
1. Sätt `POSTGRES_PASSWORD` och `DATABASE_URL` via Coolify UI/API
2. Håll lösenorden under 50 tecken
3. Efter dependency-ändringar måste du **rebuild containern**
4. Push ändringarna till Git, Coolify kommer rebuildas vid nästa deploy

### Verifiering
Efter fix, kolla logs:
```bash
# Logs ska visa:
INFO:     Started server process [8]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Dependencies
Se [pyproject.toml](./api/pyproject.toml) för aktuella versioner:
- **bcrypt==4.1.2** (explicit, för kompatibilitet)
- **passlib[bcrypt]==1.7.4**

## .env Konfiguration

**Viktigt:** `.env` filen måste finnas i `unified_platform/` katalogen för lokal Docker Compose.

Kopiera från exempel:
```bash
cp .env.example .env
# Redigera .env med dina faktiska credentials
```

För Coolify deployment används **INTE** denna .env - alla värden kommer från Coolify UI.

## Full Rebuild Efter Dependency-ändringar

Om du ändrat i `pyproject.toml`:

### Lokalt:
```bash
docker-compose -f docker-compose.unified.yml build --no-cache api worker
docker-compose -f docker-compose.unified.yml up
```

### Coolify:
1. Push ändringarna till Git
2. Gå till Coolify UI
3. Klicka "Redeploy" (det kommer bygga om containern)
