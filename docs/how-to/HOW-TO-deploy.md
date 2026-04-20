# Cómo Desplegar SysMho

## Requisitos Previos

- Python 3.12+
- Gestor de paquetes `uv`: `pip install uv`
- PostgreSQL 15+ (nativo o Docker)
- Cuenta Binance Futures (testnet para desarrollo, mainnet para producción)

---

## Opción A — PostgreSQL Nativo

### 1. Configurar entorno

```bash
# Clonar o descargar SysMho
cd SysMho

# Instalar todas las dependencias
uv sync

# Copiar plantilla de entorno
cp .env.example .env
```

### 2. Editar .env

Mínimo requerido:
```env
BINANCE_API_KEY=your_binance_testnet_api_key
BINANCE_SECRET_KEY=your_binance_testnet_secret_key
BINANCE_TESTNET=True
DB_PASSWORD=your_postgres_password
```

### 3. Inicializar base de datos

```bash
# Verificar que PostgreSQL es alcanzable
uv run db-start

# Aplicar esquema + todas las migraciones
uv run db-migrate

# (Opcional) Cargar datos de seed
uv run db-seed
```

### 4. Iniciar procesos

Abre dos terminales:

**Terminal 1 — AI Engine:**
```bash
uv run engine
```

Output esperado:
```
🧠 SysMho: Sistema Neuronal Iniciado...
✅ Modelo XGBoost cargado
🔌 Conectando WebSockets...
```

**Terminal 2 — Dashboard:**
```bash
uv run dashboard
```

Dashboard disponible en: http://localhost:8000

---

## Opción B — PostgreSQL en Docker

### 1-2. Igual que Opción A (setup + .env)

### 3. Iniciar base de datos Docker

```bash
# Iniciar PostgreSQL en Docker
uv run db-start-docker

# Aplicar esquema + migraciones a BD Docker
uv run db-migrate-docker

# (Opcional) Cargar datos de seed
uv run db-seed-docker
```

### 4. Iniciar procesos (igual que Opción A)

```bash
uv run engine
uv run dashboard
```

---

## Verificar que funciona

```bash
# Verificar salud del sistema
curl http://localhost:8000/api/system/status
# Esperado: {"api_link": "ACTIVE", ...}

# Verificar base de datos
curl http://localhost:8000/api/db/status
# Esperado: {"db_link": "ACTIVE", ...}

# O usa la skill de diagnóstico
# /sysmho
```

---

## Ir a Mainnet (dinero real)

> ⚠️ Solo hazlo después de validar 50+ operaciones en papel en testnet con buenos resultados.

### 1. Obtener claves API reales de Binance Futures
- Binance → Cuenta → Gestión de API
- Habilitar: permisos de trading de Futures
- Restringir a tu dirección IP

### 2. Actualizar .env

```env
BINANCE_API_KEY=your_real_api_key
BINANCE_SECRET_KEY=your_real_secret_key
BINANCE_TESTNET=False
```

### 3. Reiniciar engine

```bash
uv run engine
```

Verifica en los logs: `🔗 Binance: MAINNET` (no testnet).

### 4. Comenzar solo en modo manual

Establece `AUTONOMOUS_MODE=false` en `.env` inicialmente. Aprueba cada señal manualmente hasta que estés confiado en el sistema.

---

## Backups

```bash
# Backup manual de base de datos
uv run db-backup
# Guarda en: backups/sysmho_YYYYMMDD_HHMMSS.sql

# Backup de modelo (haz esto antes de reentrenar)
cp src/ai/models/xgboost_v1_1.joblib \
   src/ai/models/xgboost_v1_1_backup_$(date +%Y%m%d).joblib
```

---

## Detener el sistema

```bash
# ¡Verifica posiciones abiertas primero!
curl http://localhost:8000/api/positions

# Si no hay posiciones abiertas, detén seguramente con Ctrl+C en ambas terminales
# El engine maneja SIGINT gracefully
```

> ⚠️ Nunca detengas el engine mientras hay posiciones abiertas. Ciérralas primero desde el dashboard o espera a que SL/TP se active.

---

## Enlaces Relacionados
- `.env.example` — Todas las variables de entorno
- `docs/CONFIGURATION.md` — Referencia de configuración completa
- `docs/ARCHITECTURE.md` — Resumen del sistema
