"""
SysMho — SelfLearner (Motor de Aprendizaje Continuo).

Actualiza las estadísticas meta a partir de cada operación cerrada.
Persiste en meta_stats.json (lectura rápida por MetaEvaluator) y
en la tabla meta_stats de BD (histórico completo).

Ciclo de vida:
  1. Cuando una posición se cierra → update(trade_record)
  2. MetaEvaluator.reload_stats() → recarga el JSON actualizado
  3. Futuro (≥200 trades): entrenar meta-modelo XGBoost adicional
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from src.paths import META_STATS_PATH as _STATS_PATH, MODELS_DIR
_MIN_TRADES_META_MODEL = int(os.getenv('META_MIN_FOR_MODEL', '200'))


def _load() -> dict:
    if os.path.exists(_STATS_PATH):
        try:
            with open(_STATS_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(stats: dict) -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)
    tmp = _STATS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(stats, f, indent=2)
    os.replace(tmp, _STATS_PATH)


class SelfLearner:
    """
    Aprende de cada operación cerrada y actualiza meta_stats.json.

    Estructura del JSON:
    {
      "BTC/USDT": {
        "total_trades": 42,
        "winning_trades": 24,
        "win_rate": 0.571,
        "avg_pnl_pct": 0.0032,
        "by_hour": {
          "14_LONG": { "total": 5, "wins": 3, "win_rate": 0.6 },
          ...
        },
        "confidence_calibration": {
          "0.40": { "total": 8, "wins": 4, "win_rate": 0.5 },
          ...
        },
        "last_updated": "2026-03-30T12:00:00Z"
      }
    }
    """

    def __init__(self) -> None:
        self._stats = _load()

    def update(self, trade: dict) -> None:
        """
        Registra el resultado de un trade cerrado.

        Args:
            trade: Dict con al menos:
                symbol, direction, pnl_usdt, entry_price, exit_price,
                confidence (opcional), opened_at (ISO string o datetime)
        """
        symbol = trade.get('symbol', '')
        direction = trade.get('direction', 'LONG')
        pnl = float(trade.get('pnl_usdt', 0.0))
        confidence = float(trade.get('confidence', 0.0))
        opened_at = trade.get('opened_at')

        won = pnl > 0

        # Determinar hora UTC de apertura
        hour_utc = datetime.now(timezone.utc).hour
        if opened_at:
            try:
                if isinstance(opened_at, str):
                    dt = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
                else:
                    dt = opened_at
                hour_utc = dt.hour
            except Exception:
                pass

        if symbol not in self._stats:
            self._stats[symbol] = {
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0.0,
                'avg_pnl_pct': 0.0,
                'by_hour': {},
                'confidence_calibration': {},
                'last_updated': '',
            }

        s = self._stats[symbol]

        # ── Global ──────────────────────────────────────────────────────
        prev_total = s['total_trades']
        prev_avg = s.get('avg_pnl_pct', 0.0)

        s['total_trades'] += 1
        if won:
            s['winning_trades'] += 1
        s['win_rate'] = round(s['winning_trades'] / s['total_trades'], 4)

        # Media móvil del PnL%
        entry = float(trade.get('entry_price', 1))
        exit_p = float(trade.get('exit_price', entry))
        pnl_pct = (exit_p - entry) / entry if entry > 0 else 0.0
        if direction == 'SHORT':
            pnl_pct = -pnl_pct
        s['avg_pnl_pct'] = round(
            (prev_avg * prev_total + pnl_pct) / s['total_trades'], 6
        )

        # ── Por hora + dirección ─────────────────────────────────────────
        hk = f"{hour_utc}_{direction}"
        if hk not in s['by_hour']:
            s['by_hour'][hk] = {'total': 0, 'wins': 0, 'win_rate': 0.0}
        h = s['by_hour'][hk]
        h['total'] += 1
        if won:
            h['wins'] += 1
        h['win_rate'] = round(h['wins'] / h['total'], 4)

        # ── Calibración de confianza ─────────────────────────────────────
        if confidence > 0:
            bucket_key = f"{round(confidence / 0.05) * 0.05:.2f}"
            if bucket_key not in s['confidence_calibration']:
                s['confidence_calibration'][bucket_key] = {
                    'total': 0, 'wins': 0, 'win_rate': 0.0
                }
            c = s['confidence_calibration'][bucket_key]
            c['total'] += 1
            if won:
                c['wins'] += 1
            c['win_rate'] = round(c['wins'] / c['total'], 4)

        s['last_updated'] = datetime.now(timezone.utc).isoformat()

        _save(self._stats)

        # Verificar si hay datos suficientes para meta-modelo (futuro)
        total_all = sum(v.get('total_trades', 0) for v in self._stats.values())
        if total_all >= _MIN_TRADES_META_MODEL and total_all % 50 == 0:
            print(
                f"📈 [SelfLearner] {total_all} trades acumulados. "
                f"Meta-modelo disponible para entrenamiento."
            )

    def get_consecutive_losses(self, recent_trades: list) -> int:
        """Calcula la racha de pérdidas consecutivas más reciente (cualquier símbolo)."""
        streak = 0
        for t in reversed(recent_trades):
            if float(t.get('pnl_usdt', 0)) < 0:
                streak += 1
            else:
                break
        return streak

    def summary(self) -> dict:
        """Resumen de estadísticas globales (para dashboard)."""
        total = sum(v.get('total_trades', 0) for v in self._stats.values())
        wins = sum(v.get('winning_trades', 0) for v in self._stats.values())
        return {
            'total_trades': total,
            'global_win_rate': round(wins / total, 4) if total > 0 else 0.0,
            'symbols_tracked': len(self._stats),
            'meta_model_ready': total >= _MIN_TRADES_META_MODEL,
        }
