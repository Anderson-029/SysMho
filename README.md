# SysMho v15.2.0 — Sistema de Trading Autónomo

> Bot de trading algorítmico en Binance Futures con IA (XGBoost v3, 27 features).
> **Estado:** ✅ Operacional | **Última actualización:** Abril 3, 2026

## ¿Qué es SysMho?

SysMho es un sistema de trading algorítmico para futuros perpetuos en Binance. Combina análisis técnico multi-timeframe, inteligencia colectiva en 10 activos, modelo XGBoost entrenado con 27 features, control matemático de riesgo estricto, y motor de decisión autónomo con aprendizaje continuo.

**Dos modos operacionales:**
- **Manual**: Cada señal requiere aprobación humana via dashboard.
- **Autónomo**: MetaEvaluador puntúa estadísticamente y decide automáticamente. CircuitBreaker como red de seguridad.

**Portfolio**: BTC, ETH, BNB, SOL, XRP, ADA, AVAX, LINK, DOT, POL — todos /USDT futuros perpetuos.
**Timeframes**: 5m (predicción principal) + 1h, 4h (contexto macro).

## Inicio Rápido

### Requisitos

- Python 3.12+
- [Docker](https://docs.docker.com/get-docker/) (PostgreSQL en contenedor; recomendado)
- [uv](https://docs.astral.sh/uv/) o `pip`

### Instalación

```bash
# Clonar y entrar
git clone <repo-url> && cd SysMho

# Copiar archivo de configuración
cp .env.example .env

# Instalar dependencias
uv sync           # recomendado
# alternativa: pip install -r requirements.txt

# Base de datos (Docker) — detalle en "Base de datos"
docker compose up -d
uv run python scripts/setup_db.py
```

### Configurar `.env`

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `BINANCE_API_KEY` | Sí | Clave API Binance Futures |
| `BINANCE_SECRET_KEY` | Sí | Secreto Binance Futures |
| `BINANCE_TESTNET` | Sí | `True` testnet, `False` mainnet |
| `DB_HOST` | No | Default: `localhost` |
| `DB_PORT` | No | Default: `5432` |
| `DB_USER` | No | Default: `postgres` |
| `DB_PASSWORD` | No | Default: `postgres` |
| `DB_NAME` | No | Default: `sysmho` |

### Sincronizar BD (equipo / dump completo)

El archivo `sysmho_full.sql` (~1 GB) no va en git. Copia el dump a `src/database/seed/sysmho_full.sql` (carpeta ignorada por git) y ejecuta:

```bash
docker compose up -d
uv run python scripts/setup_db.py --seed
```

El script restaura el dump primero y luego aplica `schema.sql` y migraciones (idempotente). Ver `scripts/setup_db.py` y `src/database/AGENTS.md`.

### Iniciar

```bash
# Terminal 1: Dashboard (http://localhost:8000)
uv run uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000

# Terminal 2: Motor IA
uv run python -m src.main
```

## Base de datos

PostgreSQL corre en Docker (`docker-compose.yml`). Los datos persisten en el volumen nombrado del servicio salvo que ejecutes `docker compose down -v`.

### Primera vez (solo esquema, sin dump)

```bash
docker compose up -d
uv run python scripts/setup_db.py
```

### Uso habitual

| Acción | Comando |
|--------|---------|
| Arrancar BD | `docker compose up -d` |
| Parar BD | `docker compose down` |
| Parar y **borrar datos** | `docker compose down -v` |
| Logs | `docker compose logs -f postgres` |
| psql dentro del contenedor | `docker exec -it sysmho-postgres psql -U postgres -d sysmho` |
| Reaplicar esquema + migraciones | `uv run python scripts/setup_db.py` |

### Archivos SQL

| Archivo | Rol |
|---------|-----|
| `src/database/schema.sql` | DDL base e índices |
| `src/database/migration_v14_9_0.sql` | Categorías de alerta + score |
| `src/database/migration_v15_0_0.sql` | Índice en `model_performance` + deprecación v2 |
| `src/database/migration_v15_2_0.sql` | Tablas `autonomous_decisions` y `meta_stats` |

## Arquitectura

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

**Dos procesos independientes** se comunican via PostgreSQL y `src/runtime_state.json`:
- **Motor IA** — Datos, predicción, ejecución, monitoreo
- **Dashboard** — API REST + interfaz web

## Reentrenar Modelo

```bash
# Con hiperparámetros existentes
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m

# Con Optuna (Bayesian, ~30 min)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

Si cambias features en `src/constants.py`, elimina el modelo antes:
```bash
rm src/ai/models/xgboost_v1.joblib
```

## Tests

```bash
uv run pytest          # suite completa (50+ tests)
uv run pytest -x -v    # parar en primer fallo
```

## Modo Autónomo

Controlado via dashboard (sin reinicio):

| Componente | Rol |
|-----------|------|
| **MetaEvaluador** | 5 filtros estadísticos (WR, confianza, racha de pérdidas). Aprueba si `meta_score >= 0.52`. |
| **CircuitBreaker** | 5 stops duros: max posiciones (3), trades/día (8), pérdidas consecutivas (3), límite diario (4%), semanal (8%). |
| **SelfLearner** | Actualiza `meta_stats.json` por trade cerrado. Base para futuro meta-modelo XGBoost. |

## Configuración Clave (`src/constants.py`)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `LABEL_THRESHOLD` | 0.007 | Movimiento mínimo (0.7%) para etiquetar BUY/SELL |
| `NORMAL_MIN_CONFIDENCE` | 0.38 | Confianza mínima de señal |
| `NORMAL_RISK_PER_TRADE` | 0.02 | 2% capital en riesgo por trade |
| `NORMAL_ATR_SL` / `NORMAL_ATR_TP` | 1.5 / 3.0 | SL a 1.5x ATR, TP a 3.0x ATR |
| `NOTIONAL_CAP_RATIO` | 0.12 | Max 12% capital por trade |
| `EXPOSURE_LIMIT_RATIO` | 0.50 | Bloquea si exposición total > 50% |
| `META_SCORE_THRESHOLD` | 0.52 | Umbral aprobación MetaEvaluador |

## Migrar a Mainnet

1. Crear claves API Binance Futures con permisos de trading
2. Actualizar `.env`: `BINANCE_TESTNET=False` + claves reales
3. Reiniciar SysMho

Los recolectores de datos ya usan mainnet (endpoints públicos). Solo `trader.py` respeta `BINANCE_TESTNET`.

## Skills Agenticas

Este proyecto usa Skills agenticas para desarrollo asistido. Ver `AGENTS.md` para el router universal, índice de skills y protocolo de mantenimiento.

## Historial de Versiones

### v15.2.0 (2026-04-03) — Estable actual
**Phase 8 — Correcciones de Coherencia BD vs Binance:**
- ✅ Fix side mismatch: detecta y corrige sides invertidos entre BD y Binance
- ✅ Fix error -2022: ReduceOnly retorna False (evita posiciones zombie)
- ✅ Fix startup: _startup_reconciliation() reconcilia BD vs Binance al arrancar
- ✅ Fix portfolio: sync_wallet_from_exchange() UPDATE no-incremental

**Phase 9 — Reentrenamiento Optuna:**
- Modelo anterior: 26.1 MB, overfitting severo (35.6% confianza >0.90)
- Modelo nuevo: 8.8 MB, regularización óptima (max_depth=5, gamma=0.059)
- Resultados: 87.5% accuracy hold-out, 68.3% win rate real

**Phase 9.1 — Evaluación Relacional:**
- Skill `sysmho-model-eval`: compara versiones, emite MEJORANDO/EMPEORANDO/ESTABLE
- sysmho_full.sql: dump completo para sincronización de equipo

### v15.1.0 (2026-03-29)
- Ejecución end-to-end verificada en Binance testnet
- Telemetría de órdenes en real-time

### v15.0.0 (2026-03-29)
- Pipeline ML rediseñado: 27 features limpios, todos normalizados
- TimeSeriesSplit 5-fold validation

## Roadmap

1. Verificación Binance para mainnet trading
2. Acumular 200+ trades autónomos en testnet para entrenamiento de meta-modelo
3. Calibrar CircuitBreaker con resultados de testnet
4. Entrenar meta-modelo XGBoost en `meta_stats.json` (Phase 10)
5. Labeling adaptativo ATR en lugar de umbral fijo 0.7%

---

**Documentación detallada:** Ver `AGENTS.md` (skills), `src/AGENTS.md` (módulos), `src/ai/AGENTS.md` (pipeline ML).
