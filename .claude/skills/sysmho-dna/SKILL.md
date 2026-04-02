---
name: sysmho-dna
description: Auditoría forense completa del proyecto SysMho. Lee TODOS los archivos, audita la base de datos en vivo (esquema, datos, coherencia), mapea dependencias, y genera un reporte de ADN del proyecto que sirve como contexto total para futuras conversaciones.
---

# 🧬 SysMho DNA — Auditoría Forense Total

## Objetivo
Leer **cada archivo fuente** del proyecto SysMho sin excepción, **auditar la base de datos PostgreSQL en vivo** (esquema real, datos, integridad), entender su función, mapear sus dependencias, y producir un documento exhaustivo (`SYSMHO_DNA.md`) que sirva como **contexto total** para cualquier conversación futura.

Al cargar este documento en una nueva sesión, el asistente debe entender completamente:
- Qué hace el proyecto
- Cómo funciona internamente
- Cómo se conectan los módulos entre sí
- Dónde está cada cosa
- Qué patrones y convenciones se usan
- El estado real de la base de datos (tablas, columnas, índices, volumen de datos, frescura)
- Si el esquema en código (schema.sql) coincide con el esquema real en PostgreSQL

---

## Fase 1 — Inventario Total

Ejecuta este comando para obtener **todos** los archivos fuente del proyecto:

```bash
find /home/anderson/Documentos/programas\ personales/SysMho -type f \
  \( -name "*.py" -o -name "*.js" -o -name "*.css" -o -name "*.html" \
     -o -name "*.sql" -o -name "*.json" -o -name "*.md" -o -name "*.env*" \
     -o -name "*.toml" -o -name "*.txt" -o -name "*.yml" \) \
  ! -path "*/.git/*" ! -path "*/__pycache__/*" ! -path "*/venv/*" \
  ! -path "*/.claude/*" ! -path "*/.gemini/*" ! -path "*/.agents/*" \
  ! -path "*/.pytest_cache/*" \
  | sort
```

El resultado es el **inventario completo**. No debe quedar ningún archivo fuera.

---

## Fase 2 — Lectura Archivo por Archivo

Lee **CADA archivo** del inventario completo, uno por uno. Para cada uno, registra:

1. **Ruta completa**
2. **Propósito** — ¿Qué hace este archivo? (1-2 frases)
3. **Exports clave** — Funciones, clases, constantes que otros archivos usan
4. **Imports / Dependencias** — De qué otros archivos del proyecto depende
5. **Dependencias externas** — Librerías de terceros que usa (ej: `asyncpg`, `xgboost`)
6. **Archivos que dependen de él** — ¿Quién lo importa o consume?

### Orden de lectura obligatorio (de fundamentos a superficie):

#### Bloque 1 — Configuración y Constantes
```
.env / .env.example
config/__init__.py
config/settings.py
src/constants.py
src/runtime_config.py
src/runtime_state.json
requirements.txt
```

#### Bloque 2 — Base de Datos
```
src/database/schema.sql
src/database/repository.py
src/database/__init__.py
src/database/migration_v14_9_0.sql
src/database/migration_v15_0_0.sql
src/database/migration_v15_2_0.sql
```

#### Bloque 3 — Recolección de Datos
```
src/collector/__init__.py
src/collector/websocket.py
src/collector/backfill.py
src/collector/gap_filler.py
```

#### Bloque 4 — Análisis Técnico
```
src/analysis/__init__.py
src/analysis/indicators.py
src/analysis/features.py
```

#### Bloque 5 — Inteligencia Artificial
```
src/ai/__init__.py
src/ai/predictor.py
src/ai/trainer.py
src/ai/trainers/__init__.py
src/ai/trainers/base.py
src/ai/trainers/sequential.py
src/ai/trainers/tuner.py
src/ai/meta_evaluator.py
src/ai/self_learner.py
src/ai/backtest.py
src/ai/models/meta_stats.json
```

#### Bloque 6 — Gestión de Riesgo
```
src/risk/__init__.py
src/risk/manager.py
```

#### Bloque 7 — Ejecución de Órdenes
```
src/executor/__init__.py
src/executor/trader.py
src/executor/monitor.py
src/executor/circuit_breaker.py
```

#### Bloque 8 — Motor Principal
```
src/__init__.py
src/main.py
```

#### Bloque 9 — Dashboard API (Backend)
```
src/dashboard/__init__.py
src/dashboard/deps.py
src/dashboard/api.py
src/dashboard/routes/__init__.py
src/dashboard/routes/system.py
src/dashboard/routes/market.py
src/dashboard/routes/signals.py
src/dashboard/routes/positions.py
src/dashboard/routes/portfolio.py
src/dashboard/routes/autonomous.py
src/dashboard/routes/testing.py
```

#### Bloque 10 — Dashboard Frontend
```
src/dashboard/static/index.html
src/dashboard/static/assets/style.css
src/dashboard/static/assets/app.js
```

#### Bloque 11 — Tests
```
tests/conftest.py
tests/test_phase1.py
tests/test_phase2.py
tests/test_phase3.py
tests/test_phase4.py
tests/test_phase5.py
tests/test_phase6.py
tests/test_phase6b.py
tests/test_phase7.py
```

#### Bloque 12 — Herramientas Auxiliares
```
tools/fix_portfolio.py
tools/test_aggression.py
tools/test_connection.py
tools/verify_coherence.py
```

#### Bloque 13 — Documentación Maestra
```
SYSMHO_MANIFESTO.md
HANDOFF.md
EVOLUTION_ROADMAP.md
```

---

## Fase 2.5 — Auditoría de Base de Datos en Vivo

**CRÍTICO:** Después de leer los archivos y ANTES de mapear conexiones, conectar a PostgreSQL y ejecutar las siguientes consultas para auditar el esquema real, el volumen de datos, y la coherencia del sistema.

### 2.5.1 — Obtener credenciales de conexión

Lee el archivo `.env` del proyecto y extrae `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` para construir la cadena de conexión.

### 2.5.2 — Esquema real de la BD (tablas, columnas, tipos, constraints)

```sql
-- Query 1: Listar TODAS las tablas con conteo de filas
SELECT 
    schemaname, tablename,
    n_live_tup AS row_count_estimate
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
```

```sql
-- Query 2: Columnas de cada tabla con tipos y defaults
SELECT 
    table_name, column_name, data_type, 
    is_nullable, column_default,
    character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

```sql
-- Query 3: Índices existentes
SELECT 
    tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

```sql
-- Query 4: Constraints (PK, FK, UNIQUE, CHECK)
SELECT 
    tc.table_name, tc.constraint_name, tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage ccu 
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_type;
```

### 2.5.3 — Volumen y frescura de datos

```sql
-- Query 5: Conteo exacto de velas por símbolo y timeframe
SELECT 
    symbol, timeframe, 
    COUNT(*) as total_candles,
    MIN(open_time) as first_candle,
    MAX(open_time) as last_candle,
    EXTRACT(EPOCH FROM (NOW() - MAX(open_time))) / 60 AS minutes_since_last
FROM market_data
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

```sql
-- Query 6: Estado de la contabilidad (portfolio vs positions)
SELECT 'portfolio' as source,
       total_balance, available_balance, in_positions, total_pnl
FROM portfolio ORDER BY recorded_at DESC LIMIT 1;
```

```sql
-- Query 7: Suma real de margen en posiciones abiertas
SELECT COUNT(*) as open_positions,
       COALESCE(SUM(invested_usdt), 0) as real_margin_in_use,
       COALESCE(SUM(pnl_unrealized), 0) as floating_pnl
FROM positions;
```

```sql
-- Query 8: Estadísticas de trades cerrados
SELECT 
    COUNT(*) as total_closed,
    COUNT(*) FILTER (WHERE pnl > 0) as winners,
    COUNT(*) FILTER (WHERE pnl < 0) as losers,
    COUNT(*) FILTER (WHERE pnl = 0 OR pnl IS NULL) as breakeven,
    ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) as total_pnl,
    ROUND(COALESCE(AVG(pnl), 0)::numeric, 4) as avg_pnl,
    MIN(executed_at) as first_trade,
    MAX(executed_at) as last_trade
FROM trades WHERE status = 'CLOSED';
```

```sql
-- Query 9: Señales pendientes y historial reciente
SELECT status, COUNT(*) as count
FROM pending_approvals
GROUP BY status;
```

```sql
-- Query 10: Decisiones autónomas recientes (si la tabla existe)
SELECT decision, COUNT(*) as count,
       ROUND(AVG(meta_score)::numeric, 4) as avg_meta_score
FROM autonomous_decisions
GROUP BY decision;
```

```sql
-- Query 11: Últimos registros de rendimiento del modelo
SELECT model_name, accuracy, precision_score, recall,
       total_predictions, correct_predictions, created_at
FROM model_performance
ORDER BY created_at DESC LIMIT 10;
```

### 2.5.4 — Verificar coherencia esquema SQL vs código

Después de ejecutar las consultas, verificar que:
1. **Todas las tablas del `schema.sql`** existen realmente en PostgreSQL
2. **Las columnas coinciden** con lo que el código espera (especialmente `repository.py` y las queries en los routes)
3. **Los índices están creados** según las migraciones
4. **La contabilidad cuadra**: `portfolio.in_positions` ≈ `SUM(positions.invested_usdt)`
5. **Los datos de mercado están frescos**: `minutes_since_last` < 10 para al menos 1 símbolo

Si hay discrepancias, documentarlas en la sección "Coherencia BD" del reporte final.

---

## Fase 3 — Mapeo de Conexiones

Después de leer todos los archivos, construye estos mapas mentales:

### 3.1 Flujo de Datos Principal
Documenta el camino completo que recorre un dato desde que entra al sistema hasta que produce una acción:
```
Binance API → WebSocket/Backfill → PostgreSQL → Features → Predictor → 
MetaEvaluator → RiskManager → Trader → Binance Futures → Monitor
```
Documenta cada paso con el archivo exacto y la función responsable.

### 3.2 Grafo de Dependencias
Crea una tabla o diagrama Mermaid mostrando qué archivo importa a qué otro archivo. Identifica:
- **Archivos raíz** (no dependen de nadie interno)
- **Archivos hub** (los que más archivos importan)
- **Archivos hoja** (nadie los importa)

### 3.3 Comunicación entre Procesos
Documenta cómo se comunican los dos procesos principales:
- `main.py` (Motor de trading)
- `api.py` (Dashboard FastAPI)

Especificar: `runtime_state.json`, acceso compartido a PostgreSQL, y cualquier otro canal.

### 3.4 Ciclo de Vida del Modo Autónomo
Documenta paso a paso qué ocurre cuando el sistema opera solo:
```
Scan periódico → Señal detectada → MetaEvaluator scoring → 
Circuit Breaker check → Auto-aprobación → Ejecución → Monitor TP/SL
```

---

## Fase 4 — Generación del Reporte SYSMHO_DNA.md

**CREAR** el archivo `SYSMHO_DNA.md` en la raíz del proyecto con esta estructura exacta:

```markdown
# 🧬 SysMho DNA — Mapa Genético del Proyecto

> Generado automáticamente por auditoría forense completa.
> Última auditoría: [FECHA]
> Versión del proyecto: [VERSIÓN detectada]

## 1. Identidad del Proyecto
- Nombre, versión, stack tecnológico
- Propósito en una frase
- Modo de operación actual

## 2. Arquitectura Global
- Diagrama de alto nivel (Mermaid)
- Procesos principales y cómo se comunican
- Stack: lenguajes, frameworks, BD, APIs externas

## 3. Inventario Completo de Archivos
### Para cada archivo:
| Archivo | Propósito | Exports Clave | Depende de | Lo importan |
|---------|-----------|---------------|------------|-------------|

## 4. Flujo de Datos Principal
Paso a paso con archivos y funciones exactas.

## 5. Grafo de Dependencias
Diagrama Mermaid completo.

## 6. Módulos por Capa

### 6.1 Configuración
(Detalle de cada archivo de config)

### 6.2 Base de Datos
(Schema, repository, migraciones)

### 6.3 Recolección de Datos
(WebSocket, backfill, gap_filler)

### 6.4 Análisis Técnico
(Indicadores, features)

### 6.5 Inteligencia Artificial
(Predictor, trainer, meta_evaluator, self_learner)

### 6.6 Gestión de Riesgo
(Risk manager, position sizing)

### 6.7 Ejecución
(Trader, monitor, circuit_breaker)

### 6.8 Motor Principal
(main.py — orquestación)

### 6.9 Dashboard Backend
(API routes, deps)

### 6.10 Dashboard Frontend
(HTML, CSS, JS)

### 6.11 Tests
(Coverage por fase)

### 6.12 Herramientas
(Scripts auxiliares)

## 7. Patrones y Convenciones
- Patrones de diseño detectados
- Convenciones de nombre
- Manejo de errores
- Logging
- Estado compartido

## 8. Puntos de Configuración Críticos
- Variables de entorno
- Constantes del motor
- Parámetros del modelo
- Umbrales del Circuit Breaker

## 9. Puntos de Extensión
- Dónde agregar nuevos activos
- Dónde agregar nuevas features al modelo
- Dónde agregar nuevos endpoints
- Dónde modificar la lógica de riesgo

## 10. Auditoría de Base de Datos (En Vivo)

### 10.1 Esquema Real
Tabla completa con todas las tablas detectadas en PostgreSQL, sus columnas, tipos, 
constraints, y conteo de filas. Comparar con schema.sql.

### 10.2 Volumen de Datos
| Tabla | Filas Estimadas | Dato más antiguo | Dato más reciente |

### 10.3 Datos de Mercado por Activo
| Símbolo | Timeframe | Total Velas | Primera | Última | Frescos |

### 10.4 Estado Contable
- Balance del portfolio vs suma de posiciones abiertas
- ¿Cuadra? Diferencia si existe

### 10.5 Rendimiento del Modelo
- Últimos registros de model_performance
- Accuracy, precision, recall por modelo

### 10.6 Señales y Decisiones Autónomas
- Distribución de pending_approvals por status
- Distribución de autonomous_decisions (APPROVED vs REJECTED)

### 10.7 Coherencia Esquema vs Código
Lista de verificación:
- [ ] ¿Todas las tablas de schema.sql existen?
- [ ] ¿Las columnas coinciden con las queries del código?
- [ ] ¿Los índices están creados?
- [ ] ¿La contabilidad cuadra?
- [ ] ¿Los datos están frescos?

## 11. Estado Actual y Limitaciones Conocidas
- Bugs conocidos
- Limitaciones de testnet
- Deuda técnica identificada
- Discrepancias BD encontradas (si hay)
```

---

## Reglas Absolutas

1. **NO omitir ningún archivo.** Cada archivo del inventario debe aparecer en el reporte.
2. **NO inventar.** Solo documentar lo que se leyó. Si algo no está claro, marcarlo como `[REQUIERE REVISIÓN]`.
3. **Ser específico.** Nombres de funciones, clases y variables exactas. No generalidades.
4. **Documentar imports exactos.** Si `main.py` importa de `src.ai.predictor`, escribirlo tal cual.
5. **El documento debe ser autosuficiente.** Alguien (o un AI) que lo lea debe poder entender y trabajar en el proyecto sin leer nada más.

---

## Resultado Esperado

Al ejecutar esta skill se produce:
- **`SYSMHO_DNA.md`** en la raíz del proyecto (~documento extenso y exhaustivo)
- El asistente queda con **contexto total** del proyecto
- En futuras conversaciones, basta con decir: "lee SYSMHO_DNA.md" para tener todo el conocimiento del sistema
