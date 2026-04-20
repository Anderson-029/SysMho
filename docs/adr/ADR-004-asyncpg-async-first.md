# ADR-004: Async-First con asyncpg (sin ORM)

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

El AI Engine (`src/main.py`) maneja simultáneamente:
- 30 WebSocket feeds (10 símbolos × 3 timeframes) escuchando datos en tiempo real
- Escaneo de señales cada 5 minutos (10 activos en paralelo)
- Monitor de posiciones cada 1 segundo
- Sincronización de balance cada 5 minutos
- Auto-retraining cada hora

Un modelo de I/O síncrono bloquearía el event loop durante operaciones de BD o red, causando que los WebSockets pierdan velas o que el monitor de posiciones se retrase.

Opciones evaluadas:
- **SQLAlchemy 1.x síncrono:** Bloquea el event loop en cada query. Inaceptable para este volumen de I/O.
- **SQLAlchemy 2.0 async:** Soporte async nativo pero overhead de ORM no justificado cuando las queries son SQL puro.
- **asyncpg directo:** Máximo rendimiento, sin overhead de ORM, sintaxis clean con `pool.acquire()`.
- **Databases library:** Thin wrapper sobre asyncpg, añade abstracción sin beneficio real.

## Decision

`asyncpg` directo con pool de conexiones en `DatabaseRepository` (`src/database/repository.py`):

```python
self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

async with self.pool.acquire() as conn:
    rows = await conn.fetch(query, *params)
```

Regla: **todas las funciones que tocan BD, red o procesos externos son `async def`**.
No se usa ORM. Las queries están en SQL puro dentro de los métodos del repositorio.

## Consequences

### Positivas
- Event loop nunca bloqueado — los 30 WebSocket feeds procesan en tiempo real
- Pool de conexiones (`min_size=2, max_size=10`) maneja carga de múltiples coroutines
- Sin overhead de ORM translation — queries directas con tipos nativos Python
- `asyncpg` es uno de los drivers PostgreSQL más rápidos disponibles

### Negativas / Trade-offs
- Más verbose: cada query requiere el context manager `async with pool.acquire()`
- Sin migraciones automáticas (no hay Alembic ni equivalente) — las migraciones se escriben como SQL puro en `src/database/migration_vX_Y_Z.sql`
- Tipado manual de resultados (sin modelos ORM tipados)

### Deuda Técnica
- Si se agregan muchos métodos al repositorio, puede crecer demasiado — considerar dividirlo en repositorios por dominio (market_data, trades, positions)
- Las migrations SQL manuales son propensas a errores si no se aplican en orden
