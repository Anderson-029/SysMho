# SysMho v15.3.0 — Sistema de Trading Autónomo con Gemini Intelligence

> Bot de trading algorítmico en Binance Futures con IA (XGBoost v3 + Gemini Web Intelligence, 28 features).
> **Estado:** Operacional | **Última actualización:** Mayo 23, 2026

## ¿Qué es SysMho?

SysMho es un sistema de trading algorítmico para futuros perpetuos en Binance. Combina análisis técnico multi-timeframe, inteligencia colectiva en 10 activos, modelo XGBoost entrenado con 28 features, investigación de contexto de mercado con Gemini Intelligence (acceso web a fuentes públicas), control matemático de riesgo estricto, y motor de decisión autónomo con aprendizaje continuo.

**Dos modos operacionales:**
- **Manual**: Cada señal requiere aprobación humana via dashboard.
- **Autónomo**: MetaEvaluador puntúa estadísticamente y decide automáticamente. CircuitBreaker como red de seguridad.

**Portfolio**: BTC, ETH, BNB, SOL, XRP, ADA, AVAX, LINK, DOT, POL — todos /USDT futuros perpetuos.  
**Timeframes**: 5m (predicción principal) + 1h, 4h (contexto macro).

---

## Arquitectura

```
PostgreSQL (nativo o Docker)
    │
    ├── engine  (uv run engine)       ← AI + Trading + Learning
    │       │
    │       └── runtime_state.json    ← IPC compartido
    │       └── sysmho_brain.log      ← telemetría
    │
    └── dashboard (uv run dashboard)  ← API REST + Frontend, puerto 8000
```

| Proceso | Entry Point | Comando | Env |
|---------|------------|---------|-----|
| AI Engine | `src/main.py` | `uv run engine` | `.env` |
| Dashboard | `src/dashboard/api.py` | `uv run dashboard` | `.env` |

La base de datos puede ser PostgreSQL nativo (instalado en el sistema) o un contenedor Docker. Engine y Dashboard siempre corren localmente via `uv`.

---

## Inicio Rápido

### Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes)
- PostgreSQL 15+ (nativo **o** Docker)

### Primera vez — Opción A: PostgreSQL nativo (recomendado)

```bash
# 1. Instalar dependencias
uv sync

# 2. Crear .env desde la plantilla
cp .env.example .env     # editar claves Binance, BD y parámetros

# 3. Verificar que PostgreSQL está corriendo
uv run db-start

# 4. Aplicar schema + migraciones
uv run db-migrate

# 5. (Opcional) Cargar datos históricos
# Copiar sysmho_full.sql a src/database/seed/sysmho_full.sql
# uv run db-seed

# 6. Iniciar procesos
uv run engine       # Terminal 1: Motor IA
uv run dashboard    # Terminal 2: Dashboard → http://localhost:8000
```

### Primera vez — Opción B: PostgreSQL en Docker

```bash
# 1. Instalar dependencias
uv sync

# 2. Crear .env desde la plantilla
cp .env.example .env     # editar claves Binance, BD y parámetros

# 3. Iniciar contenedor PostgreSQL
uv run db-start-docker

# 4. Aplicar schema + migraciones (via docker exec)
uv run db-migrate-docker

# 5. (Opcional) Cargar datos históricos
# Copiar sysmho_full.sql a src/database/seed/sysmho_full.sql
# uv run db-seed-docker

# 6. Iniciar procesos
uv run engine       # Terminal 1: Motor IA
uv run dashboard    # Terminal 2: Dashboard → http://localhost:8000
```

> **Runs siguientes**: solo verificar BD (`uv run db-start` o `uv run db-status-docker`) y lanzar engine + dashboard.

---

## Comandos de gestión

Todos los comandos son entry points de `pyproject.toml`, invocados via `uv run <nombre>`.

### Base de datos — local (PostgreSQL nativo)

| Comando | Descripción |
|---------|-------------|
| `uv run db-start` | Verificar que PostgreSQL nativo es alcanzable |
| `uv run db-stop` | Instrucciones para detener PostgreSQL nativo |
| `uv run db-status` | Versión de PG + conteo de tablas via asyncpg |
| `uv run db-migrate` | Aplicar schema.sql + migraciones via asyncpg |
| `uv run db-seed` | Cargar seed data via psql local. Opcional: `--file <path>` |
| `uv run db-backup` | Dump BD via pg_dump local + copiar modelos |

### Base de datos — Docker

| Comando | Descripción |
|---------|-------------|
| `uv run db-start-docker` | Iniciar contenedor sysmho-postgres |
| `uv run db-stop-docker` | Detener contenedor |
| `uv run db-status-docker` | Estado del contenedor + conectividad PG |
| `uv run db-migrate-docker` | Aplicar schema + migraciones via docker exec psql |
| `uv run db-seed-docker` | Cargar seed via docker exec psql. Opcional: `--file <path>` |
| `uv run db-backup-docker` | Dump via docker exec pg_dump + copiar modelos |

### Aplicación

| Comando | Descripción |
|---------|-------------|
| `uv run engine` | Iniciar motor de IA (`src/main.py`) |
| `uv run dashboard` | Iniciar dashboard (uvicorn en puerto 8000) |
| `uv run test` | Ejecutar test suite (acepta argumentos extra de pytest) |

---

## Archivo de entorno

Un solo `.env` en la raíz del repo (no commiteado). Plantilla: `cp .env.example .env`. Valores por defecto (`DB_HOST=localhost`) son para desarrollo local.

Incluye: claves Binance, `DB_*`, CB/Meta, `AUTONOMOUS_MODE`, `LEARNING_LOOP_SECONDS`, `DASHBOARD_API_KEY`, etc.

---

## Base de datos

### Comandos rápidos (local)

| Acción | Comando |
|--------|---------|
| Verificar BD | `uv run db-start` |
| Aplicar schema+migraciones | `uv run db-migrate` |
| Cargar seed data | `uv run db-seed` |
| Estado de BD | `uv run db-status` |
| Backup completo | `uv run db-backup` |
| psql interactivo | `psql $DATABASE_URL` |

### Comandos rápidos (Docker)

| Acción | Comando |
|--------|---------|
| Iniciar BD | `uv run db-start-docker` |
| Aplicar schema+migraciones | `uv run db-migrate-docker` |
| Cargar seed data | `uv run db-seed-docker` |
| Estado de BD | `uv run db-status-docker` |
| Detener BD | `uv run db-stop-docker` |
| Backup completo | `uv run db-backup-docker` |

### Archivos SQL

| Archivo | Rol |
|---------|-----|
| `src/database/schema.sql` | DDL base e índices |
| `src/database/migration_v14_9_0.sql` | Categorías de alerta + score |
| `src/database/migration_v15_0_0.sql` | Índice en `model_performance` + deprecación v2 |
| `src/database/migration_v15_2_0.sql` | Tablas `autonomous_decisions` y `meta_stats` |

---

## Backup y Restore

```bash
# Crear backup completo (BD + modelos)
uv run db-backup            # PostgreSQL nativo
uv run db-backup-docker     # PostgreSQL en Docker

# Restore BD (local)
psql $DATABASE_URL < backups/sysmho_20260404_150000.sql

# Restore BD (Docker)
docker exec -i sysmho-postgres psql -U postgres -d sysmho < backups/sysmho_20260404_150000.sql
```

Los backups se guardan en `backups/` (gitignoreado). No hay limpieza automática.

---

## Arquitectura Interna

```
Binance (WebSocket + REST)
    ↓
GapFiller (llena huecos históricos)
    ↓
PostgreSQL (mercado, posiciones, trades)
    ↓
FeatureEngineer (27 features normalizadas)
    ↓
XGBoost v3 (SELL / WAIT / BUY)
    ↓
┌──────────────────┬─────────────────────┐
│ Modo Manual      │ Modo Autónomo       │
│ Aprobación       │ MetaEvaluador check │
│ via dashboard    │ CircuitBreaker      │
└────────┬─────────┴──────────┬──────────┘
         ↓                    ↓
    Trader → Binance (testnet/mainnet)
         ↓
    Monitor (loop 1s: PnL, SL/TP, sync)
         ↓
    SelfLearner → meta_stats.json
```

---

## Reentrenar Modelo

```bash
# Con hiperparámetros existentes
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m

# Con Optuna (Bayesian, ~30 min)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

Si cambias features en `src/constants.py`, elimina el modelo antes de reentrenar.

---

## Tests

```bash
uv run test              # suite completa (50+ tests)
uv run test -x -v        # parar en primer fallo
```

Tests corren en el host. `tests/conftest.py` usa `load_dotenv(".env")` para conectar a postgres en localhost (puerto 5432).

---

## Modo Autónomo

Controlado via dashboard (sin reinicio):

| Componente | Rol |
|-----------|------|
| **MetaEvaluador** | 5 filtros estadísticos (WR, confianza, racha de pérdidas). Aprueba si `meta_score >= 0.52`. |
| **CircuitBreaker** | 5 stops duros: max posiciones (3), trades/día (8), pérdidas consecutivas (3), límite diario (4%), semanal (8%). |
| **SelfLearner** | Actualiza `meta_stats.json` por trade cerrado. Base para futuro meta-modelo XGBoost. |

---

## Configuración Clave (`src/constants.py`)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `LABEL_THRESHOLD` | 0.007 | Movimiento mínimo (0.7%) para etiquetar BUY/SELL |
| `NORMAL_MIN_CONFIDENCE` | 0.38 | Confianza mínima de señal |
| `NORMAL_RISK_PER_TRADE` | 0.02 | 2% capital en riesgo por trade |
| `NORMAL_ATR_SL` / `NORMAL_ATR_TP` | 1.5 / 3.0 | SL a 1.5x ATR, TP a 3.0x ATR |
| `NOTIONAL_CAP_RATIO` | 0.12 | Max 12% capital por trade |
| `META_SCORE_THRESHOLD` | 0.52 | Umbral aprobación MetaEvaluador |

---

## Migrar a Mainnet

1. Crear claves API Binance Futures con permisos de trading
2. Editar `.env`: `BINANCE_TESTNET=False` + claves reales
3. Reiniciar engine y dashboard

Los recolectores de datos ya usan mainnet (endpoints públicos). Solo `trader.py` respeta `BINANCE_TESTNET`.

---

## Skills Agénticas

Este proyecto usa Skills agénticas para desarrollo asistido. Ver `AGENTS.md` para el router universal, índice de skills y protocolo de mantenimiento.

---

## Historial de Versiones

### v15.2.0 (2026-04-04) — Estable actual

**Phase 10 — Docker-first Architecture:**
- 3 servicios Docker: postgres, engine, dashboard (`scripts/setup_db.py` manual para DDL)
- `src/paths.py`: rutas centralizadas, compatible local y Docker
- Single `.env` for all services (template: `.env.example`)
- Engine heartbeat para healthcheck Docker
- `scripts/sysmho.py`: gestión cross-platform (start/stop/status/logs/setup/backup)
- Volumen compartido `sysmho_data` para IPC entre engine y dashboard

**Phase 8-9 — Correcciones y Reentrenamiento:**
- Fix side mismatch, ReduceOnly, startup reconciliation, portfolio sync
- Modelo reentrenado con Optuna: 87.5% accuracy, 68.3% win rate real

### v15.1.0 (2026-03-29)
- Ejecución end-to-end verificada en Binance testnet

### v15.0.0 (2026-03-29)
- Pipeline ML rediseñado: 27 features limpios, todos normalizados

---

**Documentación detallada:** Ver `AGENTS.md` (skills), `src/AGENTS.md` (módulos), `src/ai/AGENTS.md` (pipeline ML).
