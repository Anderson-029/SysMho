# Referencia de API de SysMho

**URL Base:** `http://localhost:8000`
**Versión:** 15.2.0
**Autenticación:** Header `X-API-Key: <your-key>` (establece `DASHBOARD_API_KEY` en `.env`)
Si `DASHBOARD_API_KEY` está vacío → acceso abierto (modo desarrollo).

---

## Sistema

### GET /api/system/status
Verifica la conexión activa con la API de Binance.

**Auth:** Requerida
**Response 200:**
```json
{
  "api_link": "ACTIVE",
  "last_check": 1745177234.5
}
```
**Valores `api_link`:** `"ACTIVE"` | `"RECONNECTING"` | `"DISCONNECTED"` | `"INVALID_KEYS"`

**Ejemplo:**
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/system/status
```

---

### GET /api/system/last_scan
Retorna el timestamp del último escaneo de señales REGULAR.

**Auth:** Requerida
**Response 200:**
```json
{
  "last_scan_ts": 1745177100.0,
  "next_scan_in": 183.5
}
```
`next_scan_in`: segundos hasta el próximo escaneo (ciclo de 300s).

---

### GET /api/data/freshness
Verifica la frescura de datos de velas 5m por símbolo.

**Auth:** Requerida
**Response 200:**
```json
{
  "status": "FRESH",
  "max_age_seconds": 145,
  "symbols": [
    {"symbol": "BTC/USDT", "last_candle": "2026-04-20T18:35:00+00:00", "age_seconds": 145}
  ],
  "checked_at": 1745177234.5
}
```
**Valores `status`:** `"FRESH"` (<330s) | `"DELAYED"` (330-900s) | `"STALE"` (>900s) | `"ERROR"`

---

### GET /api/db/status
Verifica la salud de la conexión PostgreSQL.

**Auth:** Requerida
**Response 200:**
```json
{"db_link": "ACTIVE", "last_check": 1745177234.5}
```
**Valores `db_link`:** `"ACTIVE"` | `"DISCONNECTED"`

---

### GET /api/system/sync_status
Retorna el estado de sincronización del Gap Filler.

**Auth:** Requerida
**Response 200:**
```json
{"status": "idle"}
```
O mientras se sincroniza:
```json
{"status": "syncing", "detail": "BTC/USDT 5m (3/30)"}
```

---

### GET /api/logs
Lee el log de telemetría neuronal (sysmho_brain.log).

**Auth:** Requerida
**Parámetros query:** `limit` (int, default: 500) — número de líneas recientes a retornar

**Response 200:**
```json
{
  "logs": [
    "[13:37:00] ✅ [GAP FILLER] Sincronización completa — 34500 velas insertadas",
    "[13:42:15] 🧠 [SCAN] BTC/USDT → BUY confidence=0.62"
  ]
}
```

**Ejemplo:**
```bash
curl -H "X-API-Key: your-key" "http://localhost:8000/api/logs?limit=100"
```

---

## Datos de Mercado

### GET /api/market_data/{symbol_encoded}
Retorna datos de velas OHLCV para gráficos.

**Auth:** Requerida
**Parámetros path:**
- `symbol_encoded` (int): Índice del símbolo — BTC=0, ETH=1, BNB=2, SOL=3, XRP=4, ADA=5, AVAX=6, LINK=7, DOT=8, POL=9

**Parámetros query:**
- `timeframe` (str, default: `"5m"`): `"5m"` | `"1h"` | `"4h"`
- `limit` (int, default: 288): número de velas (288 = 24h de velas 5m)

**Response 200:**
```json
[
  {"time": 1745100000, "open": 84500.0, "high": 85100.0, "low": 84200.0, "close": 84900.0, "volume": 1234.5}
]
```

**Ejemplo:**
```bash
# Obtener últimas 100 velas 5m de ETH/USDT (symbol_encoded=1)
curl -H "X-API-Key: your-key" "http://localhost:8000/api/market_data/1?timeframe=5m&limit=100"
```

---

## Señales

### GET /api/pending_signals
Lista señales de IA pendientes ordenadas por prioridad (BOUNTY primero, luego REGULAR por score).

**Auth:** Requerida
**Response 200:**
```json
[
  {
    "id": 42,
    "symbol": "BTC/USDT",
    "side": "BUY",
    "quantity": 0.001,
    "entry_price": 84500.0,
    "stop_loss": 83800.0,
    "take_profit": 86200.0,
    "risk_score": 0.73,
    "invested_usdt": 84.5,
    "win_probability": 0.62,
    "loss_probability": 0.38,
    "potential_profit_usdt": 1.70,
    "potential_loss_usdt": 0.70,
    "alert_category": "BOUNTY",
    "score": 0.81,
    "signal_type": "PREMIUM",
    "trend_5m": "UP", "trend_1h": "UP", "trend_4h": "UP",
    "created_at": "2026-04-20T18:40:00+00:00"
  }
]
```

---

### POST /api/signals/{id}/approve
Aprueba una señal pendiente para ejecución.

**Auth:** Requerida
**Parámetros path:** `id` (int): signal ID de pending_signals

**Response 200:**
```json
{"message": "Señal aprobada", "symbol": "BTC/USDT", "side": "BUY"}
```
**Errores:** 404 Señal no encontrada o ya procesada

---

### POST /api/signals/{id}/reject
Rechaza una señal pendiente.

**Auth:** Requerida
**Parámetros path:** `id` (int): signal ID

**Response 200:**
```json
{"message": "Señal rechazada", "symbol": "BTC/USDT", "side": "BUY"}
```

---

### POST /api/signals/dismiss_all
Limpia todas las señales PENDING visualmente (marca como DISMISSED). No afecta datos de entrenamiento.

**Auth:** Requerida
**Response 200:**
```json
{"dismissed": 3}
```

---

### GET /api/authorized_history
Retorna últimas 10 señales procesadas (APPROVED/EXECUTED/FAILED/REJECTED).

**Auth:** Requerida
**Response 200:**
```json
[
  {
    "id": 41,
    "symbol": "ETH/USDT",
    "side": "SELL",
    "status": "EXECUTED",
    "resolved_at": "2026-04-20T17:55:00+00:00"
  }
]
```

---

## Posiciones

### GET /api/positions
Retorna todas las posiciones abiertas actualmente.

**Auth:** Requerida
**Response 200:**
```json
[
  {
    "symbol": "BTC/USDT",
    "side": "BUY",
    "entry_price": 84500.0,
    "current_price": 84900.0,
    "quantity": 0.001,
    "stop_loss": 83800.0,
    "take_profit": 86200.0,
    "pnl_unrealized": 0.40,
    "invested_usdt": 84.5,
    "leverage": 1,
    "opened_at": "2026-04-20T16:30:00+00:00"
  }
]
```

---

### POST /api/positions/{symbol_encoded}/close
Cierra manualmente una posición abierta.

**Auth:** Requerida
**Parámetros path:** `symbol_encoded` (str): ej. `"BTC_USDT"` (slash reemplazado con underscore)

**Response 200:**
```json
{"message": "Posición cerrada", "symbol": "BTC/USDT"}
```
**Errores:** 404 Posición no encontrada

---

## Portafolio

### GET /api/balance
Retorna el balance operativo actual.

**Auth:** Requerida
**Response 200:**
```json
{
  "available_balance": 245.50,
  "currency": "USDT"
}
```

---

### GET /api/stats
Retorna KPIs macro: win rate, PnL, operaciones activas, PnL diario y tasas de divisa.

**Auth:** Requerida
**Response 200:**
```json
{
  "win_rate": 0.58,
  "pnl_realizado": 12.45,
  "floating_pnl": 0.40,
  "active_trades": 1,
  "pnl_diario": 3.20,
  "total_balance": 258.35,
  "usd_to_cop": 4150.0,
  "usd_to_eur": 0.92
}
```

---

### GET /api/trades/history
Retorna últimas 10 operaciones cerradas.

**Auth:** Requerida
**Response 200:**
```json
[
  {
    "id": 38,
    "symbol": "SOL/USDT",
    "side": "BUY",
    "entry_price": 142.5,
    "close_price": 145.2,
    "pnl": 1.89,
    "executed_at": "2026-04-20T14:20:00+00:00"
  }
]
```

---

### POST /api/portfolio/transfer_to_reserve
Transfiere capital operativo de vuelta al fondo de reserva (resetea balance operativo a 0).

**Auth:** Requerida
**Response 200:**
```json
{"message": "Capital transferido a reserva"}
```

---

### POST /api/portfolio/reset_pnl
Reinicia el contador de PnL diario (escribe timestamp a runtime_state.json).

**Auth:** Requerida
**Response 200:**
```json
{"message": "PnL diario reiniciado", "reset_at": "2026-04-20T00:00:00+00:00"}
```

---

### POST /api/portfolio/adjust_capital
Ajusta capital operativo usando la tasa de cambio COP→USDT en vivo.

**Auth:** Requerida
**Body:**
```json
{"capital_cop": 500000}
```
**Response 200:**
```json
{"message": "Capital ajustado", "usdt_added": 120.48}
```

---

## Modo Autónomo

### GET /api/autonomous/status
Retorna estado del modo autónomo, stats de MetaEvaluador, estado del CircuitBreaker y resumen del SelfLearner.

**Auth:** Requerida
**Response 200:**
```json
{
  "autonomous_mode": true,
  "circuit_breaker": {
    "max_positions": 3,
    "max_daily_trades": 8,
    "max_consec_losses": 3,
    "daily_loss_pct": 0.04,
    "weekly_drawdown_pct": 0.08
  },
  "daily_stats": {
    "trades_today": 2,
    "daily_pnl_pct": 0.012,
    "consecutive_losses": 0
  },
  "learner_summary": {
    "total_trades": 87,
    "global_win_rate": 0.575,
    "symbols_tracked": 8,
    "meta_model_ready": false
  }
}
```

---

### GET /api/autonomous/decisions
Retorna historial de decisiones del MetaEvaluador.

**Auth:** Requerida
**Parámetros query:** `limit` (int, default: 50)

**Response 200:**
```json
[
  {
    "symbol": "BTC/USDT",
    "meta_score": 0.634,
    "confidence": 0.58,
    "approved": true,
    "trade_pnl": 1.45,
    "created_at": "2026-04-20T16:30:00+00:00"
  }
]
```

---

### POST /api/autonomous/toggle
Habilita o deshabilita el modo autónomo en tiempo de ejecución (sin reinicio del engine requerido).

**Auth:** Requerida
**Body:**
```json
{"enable": true}
```
**Response 200:**
```json
{"autonomous_mode": true, "message": "Modo autónomo activado"}
```

---

### POST /api/autonomous/reset_cb
Reinicia los contadores del Circuit Breaker (operaciones hoy, PnL, pérdidas consecutivas → 0).

**Auth:** Requerida
**Response 200:**
```json
{"message": "Circuit Breaker reiniciado"}
```

---

## Testing

### POST /api/test/inject_signal
Inyecta una señal TEST al pool PENDING (simula predicción de IA para validación de UI/Risk).

**Auth:** Requerida
**Body:**
```json
{"symbol": "BTC/USDT", "side": "BUY"}
```
**Response 200:**
```json
{"message": "Señal de prueba inyectada", "id": 99}
```

> ⚠️ Solo usar en desarrollo/testnet. Esta señal puede ser aprobada y ejecutada.

---

## Códigos de Error

| Código | Significado |
|--------|------------|
| 200 | Éxito |
| 403 | X-API-Key inválida o faltante |
| 404 | Recurso no encontrado |
| 500 | Error interno del servidor (revisa `/api/logs` para detalles) |
