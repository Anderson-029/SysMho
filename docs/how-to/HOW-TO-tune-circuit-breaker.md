# Cómo Calibrar el Circuit Breaker

## Cuándo usar esta guía

- El CB se dispara muy seguido en condiciones normales de mercado (muy conservador)
- El CB nunca se dispara incluso durante malas condiciones de mercado (muy permisivo)
- Después de un período de drawdown: revisar si los thresholds protegieron capital o fueron inadecuados
- Después de agregar más símbolos (más posiciones posibles → puede que necesites aumentar límites)

---

## Entendimiento de los 5 Componentes del CB

Todos los 5 stops se evalúan en orden. El primero que se activa bloquea el engine.

| Componente | Clave `.env` | Default | Se activa cuando... |
|-----------|-----------|---------|------------------|
| Drawdown diario | `CB_DAILY_LOSS_PCT` | `0.04` (4%) | PnL diario ≤ -4% del capital |
| Drawdown semanal | `CB_WEEKLY_DRAWDOWN_PCT` | `0.08` (8%) | PnL semanal ≤ -8% del capital |
| Pérdidas consecutivas | `CB_MAX_CONSEC_LOSSES` | `3` | 3 pérdidas seguidas sin una ganancia |
| Posiciones abiertas | `CB_MAX_OPEN_POSITIONS` | `3` | 3 posiciones abiertas simultáneamente |
| Trades diarios | `CB_MAX_DAILY_TRADES` | `8` | 8 operaciones ejecutadas hoy |

---

## Paso 1: Diagnosticar comportamiento actual del CB

```bash
# Verificar historial de CB y sugerencia
/sysmho-cb-tune

# Verificar rendimiento
/sysmho-performance
```

Busca:
- ¿Cuántas veces se disparó el CB esta semana?
- ¿Cuál fue la razón cada vez?
- ¿Eran esos disparos justificados (drawdown real) o falsos positivos (volatilidad normal)?

---

## Paso 2: Analizar el historial de operaciones

```bash
# Ver operaciones recientes
curl http://localhost:8000/api/trades/history

# Ver decisiones autónomas
curl http://localhost:8000/api/autonomous/decisions?limit=50
```

Preguntas a responder:
- ¿Después de cuántas pérdidas consecutivas se disparó el CB? ¿El mercado era realmente malo?
- ¿Se disparó el CB en drawdown diario antes de que el mercado se recuperara el mismo día?

---

## Paso 3: Ajustar parámetros en .env

Edita `.env` con tus nuevos valores:

```env
# Ejemplo: ligeramente más permisivo
CB_DAILY_LOSS_PCT=0.05        # Permitir hasta 5% de pérdida diaria
CB_MAX_CONSEC_LOSSES=4        # Permitir 4 pérdidas consecutivas antes de detener
```

### Guía por tipo de mercado

**Mercado ranging/choppy (muchas pérdidas pequeñas):**
```env
CB_MAX_CONSEC_LOSSES=4        # Aumenta: las pérdidas consecutivas son normales en ranging
CB_MAX_DAILY_TRADES=6         # Disminuye: reducir overtrading
```

**Mercado trending (grandes movimientos):**
```env
CB_DAILY_LOSS_PCT=0.04        # Mantén: proteger contra reversiones de tendencia
CB_MAX_OPEN_POSITIONS=4       # Aumenta: permitir más posiciones en tendencia fuerte
```

**Capital ajustado (cuenta pequeña):**
```env
CB_DAILY_LOSS_PCT=0.03        # Disminuye: proteger más agresivamente
CB_WEEKLY_DRAWDOWN_PCT=0.06
CB_MAX_DAILY_TRADES=5
```

### Límites duros (nunca exceder):

| Parámetro | Max Recomendado |
|-----------|-----------------|
| `CB_DAILY_LOSS_PCT` | 0.10 (10%) — sobre esto, riesgo de liquidación |
| `CB_WEEKLY_DRAWDOWN_PCT` | 0.20 (20%) |
| `CB_MAX_CONSEC_LOSSES` | 6 |
| `CB_MAX_DAILY_TRADES` | 15 |
| `CB_MAX_OPEN_POSITIONS` | 5 |

---

## Paso 4: Aplicar cambios

### Opción A — Reiniciar engine (recarga completa)

```bash
# Detener engine (Ctrl+C en terminal del engine)
uv run engine
```

### Opción B — Resetear contadores del CB sin reinicio (si engine está corriendo)

Desde el dashboard:
```bash
curl -X POST http://localhost:8000/api/autonomous/reset_cb
```

Esto reseta: operaciones de hoy, pérdidas consecutivas, contador PnL diario → 0.
Los nuevos valores `.env` se aplican en el próximo reinicio del engine.

---

## Paso 5: Monitorear después del cambio

Para las próximas 24-48 horas, observa:
- ¿Se disparó el CB menos frecuentemente mientras sigue protegiendo contra drawdowns reales?
- ¿Mejoró el PnL diario (menos detenciones falsas)?

```bash
# Monitoreo en tiempo real
/sysmho-logs

# Rendimiento después de 48h
/sysmho-performance
```

---

## Enlaces Relacionados
- `docs/adr/ADR-003-circuit-breaker-pattern.md` — Decisiones de diseño detrás del CB
- `src/executor/circuit_breaker.py` — Implementación
- `docs/CONFIGURATION.md` — Descripción de todos los parámetros del CB
- `/sysmho-cb-tune` — Skill de análisis automático del CB
