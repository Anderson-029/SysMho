---
name: sysmho-metrics
description: Muestra el pipeline completo de predicción, las 28 features del modelo, umbrales del predictor, umbrales dinámicos del MetaEvaluador por activo y estado actual del CircuitBreaker.
allowed-tools: Read Bash
---

Genera un reporte completo de todas las métricas que SysMho usa para hacer sus predicciones y decisiones de trading.

## PASO 1 — Leer constantes del sistema

Lee `src/constants.py` y extrae:
- `MODEL_FEATURES` (lista de 28 features)
- `NORMAL_MIN_CONFIDENCE`, `NORMAL_INERTIA_THRESHOLD`, `NORMAL_STRENGTH_RATIO`, `HIGH_CONVICTION_THRESHOLD`
- `META_SCORE_THRESHOLD`, `MIN_TRADES_FOR_STATS` (de meta_evaluator.py: `META_MIN_TRADES=10`)
- `DESTRUCTIVE_HOUR_START`, `DESTRUCTIVE_HOUR_END`, `DESTRUCTIVE_HOUR_PENALTY`
- `SYMBOLS` y `SYMBOL_ENCODING`

## PASO 2 — Leer métricas históricas del MetaEvaluador

Lee `src/ai/models/meta_stats.json` y extrae para cada símbolo:
- `total_trades`
- `winning_trades`
- `win_rate`

## PASO 3 — Calcular umbrales dinámicos

Para cada símbolo ejecuta este script Python inline:

```bash
uv run python - <<'EOF'
import json, os
from datetime import datetime, timezone

with open('src/ai/models/meta_stats.json') as f:
    stats = json.load(f)

BASE = 0.52
MIN_TRADES = 10
PENALTY = 0.08
DH_START, DH_END = 14, 17
hour = datetime.now(timezone.utc).hour
in_window = DH_START <= hour < DH_END

symbols = ['BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT',
           'ADA/USDT','AVAX/USDT','LINK/USDT','DOT/USDT','POL/USDT']
encoding = {'BTC/USDT':0,'ETH/USDT':1,'BNB/USDT':2,'SOL/USDT':3,'XRP/USDT':4,
            'ADA/USDT':5,'AVAX/USDT':6,'LINK/USDT':7,'DOT/USDT':8,'POL/USDT':9}

print(f"hora_utc={hour} en_ventana={in_window}")
print()
print(f"{'Activo':<12} {'WR':>7} {'Trades':>7} {'Base':>7} {'Ventana':>8} {'Final':>7} {'Nota'}")
print("-" * 65)
for sym in symbols:
    s = stats.get(sym, {})
    total = s.get('total_trades', 0)
    wr = s.get('win_rate', None)
    if total >= MIN_TRADES and wr is not None:
        base = round(BASE + max(0.0, (0.50 - wr) * 0.40), 4)
        note = ""
    else:
        base = BASE
        wr = None
        note = f"* insuf ({total} trades)"
    penalty_str = f"+{PENALTY:.2f}" if in_window else "—"
    final = round(min(base + (PENALTY if in_window else 0.0), 0.75), 4)
    wr_str = f"{wr*100:.1f}%" if wr is not None else "—"
    print(f"{sym:<12} {wr_str:>7} {total:>7} {base:>7.4f} {penalty_str:>8} {final:>7.4f} {note}")
EOF
```

## PASO 4 — Estado del CircuitBreaker en vivo

Obtén los límites del `.env` o usa defaults, y consulta la BD para el estado actual:

```bash
# Leer límites del .env
grep -E "^CB_" .env 2>/dev/null || echo "Usando defaults: MAX_POSITIONS=3 MAX_DAILY_TRADES=8 MAX_CONSEC_LOSSES=3 DAILY_LOSS_PCT=4% WEEKLY_DRAWDOWN_PCT=8%"
```

```bash
uv run python - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from datetime import datetime, timezone

db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Posiciones abiertas
cur.execute("SELECT COUNT(*) FROM positions")
open_pos = cur.fetchone()[0]

# Trades hoy y PnL diario
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(pnl_usdt), 0)
    FROM trades
    WHERE status = 'CLOSED' AND closed_at >= NOW() - INTERVAL '24 hours'
""")
daily_trades, daily_pnl = cur.fetchone()

# PnL semanal
cur.execute("""
    SELECT COALESCE(SUM(pnl_usdt), 0)
    FROM trades
    WHERE status = 'CLOSED' AND closed_at >= NOW() - INTERVAL '7 days'
""")
weekly_pnl = cur.fetchone()[0]

# Últimas 5 operaciones para calcular pérdidas consecutivas
cur.execute("""
    SELECT pnl_usdt FROM trades
    WHERE status = 'CLOSED'
    ORDER BY closed_at DESC LIMIT 5
""")
rows = cur.fetchall()
consec = 0
for (pnl,) in rows:
    if float(pnl) < 0:
        consec += 1
    else:
        break

# Balance para calcular %
cur.execute("SELECT total_balance FROM portfolio ORDER BY recorded_at DESC LIMIT 1")
row = cur.fetchone()
balance = float(row[0]) if row else 1

daily_pnl_pct = float(daily_pnl) / balance * 100
weekly_pnl_pct = float(weekly_pnl) / balance * 100

# Límites
max_pos = int(os.getenv('CB_MAX_POSITIONS', 3))
max_trades = int(os.getenv('CB_MAX_DAILY_TRADES', 8))
max_consec = int(os.getenv('CB_MAX_CONSEC_LOSSES', 3))
daily_limit = float(os.getenv('CB_DAILY_LOSS_PCT', 0.04)) * 100
weekly_limit = float(os.getenv('CB_WEEKLY_DRAWDOWN_PCT', 0.08)) * 100

def status(val, limit, invert=False):
    ok = val <= limit if not invert else val >= limit
    return "✅" if ok else "🔴"

print(f"  Pérdida diaria:          {daily_pnl_pct:+.2f}%  / límite {-daily_limit:.1f}%   {status(daily_pnl_pct, -daily_limit)}")
print(f"  Drawdown semanal:        {weekly_pnl_pct:+.2f}%  / límite {-weekly_limit:.1f}%   {status(weekly_pnl_pct, -weekly_limit)}")
print(f"  Pérdidas consecutivas:   {consec}      / máximo {max_consec}        {'✅' if consec < max_consec else '🔴'}")
print(f"  Posiciones abiertas:     {open_pos}      / máximo {max_pos}        {'✅' if open_pos < max_pos else '🔴'}")
print(f"  Trades hoy:              {daily_trades}      / máximo {max_trades}        {'✅' if daily_trades < max_trades else '🔴'}")

triggered = (
    daily_pnl_pct <= -daily_limit or
    weekly_pnl_pct <= -weekly_limit or
    consec >= max_consec or
    open_pos >= max_pos or
    daily_trades >= max_trades
)
print()
print(f"  ESTADO CB: {'🔴 BLOQUEADO' if triggered else '🟢 OPERACIONAL'}")

cur.close()
conn.close()
EOF
```

## PASO 5 — Leer estado de autonomía

Lee `src/runtime_state.json` y extrae:
- `autonomous_mode` (true/false)
- `sync_status`
- `last_scan_at`

## PASO 6 — Mostrar reporte completo

Con todos los datos recopilados, presenta el reporte en este formato:

```
══════════════════════════════════════════════════════════════════
  SYSMHO METRICS — [FECHA Y HORA UTC]
══════════════════════════════════════════════════════════════════

🔁 PIPELINE DE PREDICCIÓN (5 etapas)
──────────────────────────────────────────────────────────────────
  OHLCV 5m
    └─ [1] FeatureEngineer  → 28 features (indicadores técnicos + macro 1h/4h + swarm + identidad)
    └─ [2] ModelPredictor   → probabilidades [SELL, WAIT, BUY] con 3 filtros de calidad
    └─ [3] MetaEvaluador    → meta_score (5 componentes) vs umbral dinámico por activo
    └─ [4] CircuitBreaker   → 5 condiciones de protección de capital
    └─ [5] TradeExecutor    → EJECUTAR / RECHAZAR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 FEATURES DEL MODELO (28 features — XGBoost v3)
──────────────────────────────────────────────────────────────────
  Momentum 5m      (3)  rsi_14 | stoch_rsi_k | macd_diff_pct
                        RSI-14 / StochRSI K (smoothed 3/3) / histograma MACD normalizado (% precio)

  Tendencia 5m     (3)  adx | adx_pos | bb_pband
                        Fuerza tendencia ADX-14 / componente alcista DI+ / posición Bollinger (0=bajo, 1=alto)

  Precio 5m        (6)  atr_pct | ema_21_dist | ema_200_dist | vwap_dist | pct_change | vol_change
                        Todos normalizados como % del precio (sin sesgo de escala BTC vs POL)

  Futuros          (2)  funding_rate | obi_20
                        Sesgo largo/corto del mercado / desequilibrio libro de órdenes

  Swarm            (3)  swarm_rsi_avg | swarm_macd_avg | swarm_bull_ratio
                        Promedios de los otros 9 activos → detecta tendencia del portafolio completo

  Macro 1h         (5)  h1_rsi_14 | h1_macd_diff_pct | h1_adx | h1_bb_pband | h1_atr_pct
                        Mismo set de indicadores en temporalidad 1h (merge ASOF por timestamp)

  Macro 4h         (5)  h4_rsi_14 | h4_macd_diff_pct | h4_adx | h4_bb_pband | h4_atr_pct
                        Mismo set de indicadores en temporalidad 4h (merge ASOF por timestamp)

  Identidad        (1)  symbol_encoded
                        Entero estable: BTC=0, ETH=1, BNB=2, SOL=3, XRP=4, ADA=5, AVAX=6, LINK=7, DOT=8, POL=9

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📐 UMBRALES DEL PREDICTOR (MODO NORMAL)
──────────────────────────────────────────────────────────────────
  Confianza mínima (min_conf):    [NORMAL_MIN_CONFIDENCE]   → clase dominante debe superar esto
  Inercia (WAIT veto):            [NORMAL_INERTIA_THRESHOLD] → si P(WAIT) > umbral → WAIT automático
  Strength ratio:                 [NORMAL_STRENGTH_RATIO]×  → prob_dom / prob_opuesta ≥ ratio
  Alta convicción:                [HIGH_CONVICTION_THRESHOLD] → aprueba sin ratio si supera esto
  MetaScore aprobación base:      [META_SCORE_THRESHOLD]

  Fórmula Filtro 3:
    is_impulse      = (prob_dom ≥ min_conf) AND (prob_dom / prob_opuesta ≥ ratio)
    is_high_conv    = prob_dom ≥ alta_conviccion
    Si ninguno      → WAIT (señal descartada)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ VENTANA HORARIA DESTRUCTIVA
──────────────────────────────────────────────────────────────────
  Rango UTC:         [DESTRUCTIVE_HOUR_START]:00 – [DESTRUCTIVE_HOUR_END-1]:59
  WR histórico:      33% (vs 42% global) — causa 75% del drawdown histórico
  Penalización:      +[DESTRUCTIVE_HOUR_PENALTY] al umbral MetaEvaluador cuando activa
  Hora actual UTC:   [hora_utc]  ← [EN VENTANA 🔴 / FUERA DE VENTANA ✅]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 META EVALUADOR — 5 Componentes del Score
──────────────────────────────────────────────────────────────────
  meta_score = media de:
    [1] Win rate global del símbolo         (de meta_stats.json → win_rate)
    [2] Win rate por hora UTC + dirección   (de meta_stats.json → by_hour["{h}_{dir}"])
    [3] Calibración confianza               (¿el modelo acertó cuando dijo X%?)
    [4] Racha pérdidas recientes            (−8% por cada pérdida >1 en últimas 5)
    [5] Confianza base × 1.2               (crédito directo al XGBoost)

  Umbral dinámico = 0.52 + max(0, (0.50 − WR_activo) × 0.40), cap 0.75
                  + 0.08 si hora ∈ [14, 17) UTC

🤖 META EVALUADOR — Umbrales por Activo
──────────────────────────────────────────────────────────────────
  [tabla generada en PASO 3]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 CIRCUIT BREAKER — Estado Actual
──────────────────────────────────────────────────────────────────
  [datos del PASO 4]

  Autonomía: [autonomous_mode de runtime_state.json → HABILITADA ✅ / DESHABILITADA ⚠️]
  Último scan: [last_scan_at]

══════════════════════════════════════════════════════════════════
```

Sustituye todos los valores entre `[...]` con los datos reales obtenidos en los pasos anteriores.
