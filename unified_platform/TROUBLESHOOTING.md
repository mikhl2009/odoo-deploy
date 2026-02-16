# Docker och Deployment Troubleshooting

## Bcrypt Password Längd Problem

### Problem
Om du ser följande fel under startup:
```
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```

### Root Cause
- Bcrypt har en inbyggd begränsning på max 72 bytes för lösenord
- Passlib 1.7.4 med vissa bcrypt-versioner kan få version compatibility issues
- Långa miljövariabler (speciellt `POSTGRES_PASSWORD`) kan trigga detta fel

### Lösning
**Håll alla lösenord under 50 tecken för maximal kompatibilitet**

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
3. Efter varje ändring, restarta applikationen
4. Coolify kan auto-generera långa lösenord - ändra dem manuellt

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
- passlib[bcrypt]==1.7.4
- bcrypt (installerad som passlib dependency)

## .env Konfiguration

**Viktigt:** `.env` filen måste finnas i `unified_platform/` katalogen för Docker Compose.

Kopiera från exempel:
```bash
cp .env.example .env
# Redigera .env med dina faktiska credentials
```
