"""
SysMho — MetaEvaluador (Capa de Aprobación Autónoma).

Evalúa una señal usando estadísticas históricas propias del sistema
y devuelve un meta_score + decisión de aprobación.

No reemplaza al modelo XGBoost principal — es una segunda capa de filtro
que decide si la señal del modelo merece ser ejecutada de forma autónoma.

Criterios evaluados:
  1. Win Rate histórico del símbolo (si hay suficientes datos)
  2. Win Rate por hora UTC del símbolo + dirección
  3. Calibración de confianza (¿el modelo acertó cuando dijo X%?)
  4. Racha de pérdidas recientes
  5. Contexto de mercado en el día actual
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Umbral mínimo de meta_score para aprobar (override por .env)
def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


META_SCORE_THRESHOLD = _env_float('META_SCORE_THRESHOLD', 0.52)
MIN_TRADES_FOR_STATS = int(os.getenv('META_MIN_TRADES', '10'))

from src.paths import META_STATS_PATH as _STATS_PATH


def _load_stats() -> dict:
    if os.path.exists(_STATS_PATH):
        try:
            with open(_STATS_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


class MetaEvaluator:
    """
    Filtro estadístico de segunda capa para aprobación autónoma.

    Uso:
        evaluator = MetaEvaluator()
        score, approved, reasons = evaluator.evaluate(signal_dict)
    """

    def __init__(self) -> None:
        self._stats: dict = _load_stats()

    def reload_stats(self) -> None:
        """Recarga estadísticas desde disco (llamar tras SelfLearner.update)."""
        self._stats = _load_stats()

    def evaluate(
        self,
        signal: dict,
        recent_trades: Optional[List[dict]] = None,
        window_penalty: float = 0.0,
    ) -> Tuple[float, bool, List[str]]:
        """
        Evalúa una señal y devuelve (meta_score, approved, reasons).

        Args:
            signal: Diccionario de la señal (campos de pending_approvals).
            recent_trades: Últimas N operaciones cerradas (para racha y contexto).
            window_penalty: Penalty adicional al umbral dinámico (ej. 0.08 en ventana
                            horaria destructiva). Temporal hasta acumular datos by_hour.

        Returns:
            meta_score [0..1], approved (bool), reasons (lista de strings)
        """
        reasons: List[str] = []
        score_components: List[float] = []

        symbol = signal.get('symbol', '')
        # pending_approvals usa 'side' (BUY/SELL) y 'win_probability' (no direction/confidence)
        side = signal.get('side', 'BUY')
        direction = signal.get('direction') or ('LONG' if side == 'BUY' else 'SHORT')
        confidence = float(
            signal.get('win_probability') or signal.get('confidence') or 0.0
        )
        hour_utc = datetime.now(timezone.utc).hour

        sym_stats = self._stats.get(symbol, {})
        total = sym_stats.get('total_trades', 0)

        # ── 1. Win rate global del símbolo ──────────────────────────────
        if total >= MIN_TRADES_FOR_STATS:
            wr = sym_stats.get('win_rate', 0.5)
            score_components.append(wr)
            if wr >= 0.55:
                reasons.append(f"✅ Win rate {symbol}: {wr*100:.1f}%")
            elif wr <= 0.45:
                reasons.append(f"⚠️ Win rate bajo {symbol}: {wr*100:.1f}%")
        else:
            # Sin datos suficientes → neutro (0.5)
            score_components.append(0.50)
            reasons.append(f"ℹ️ Datos insuficientes {symbol} ({total} trades)")

        # ── 2. Win rate por hora + dirección ────────────────────────────
        hour_key = f"{hour_utc}_{direction}"
        hour_stats = sym_stats.get('by_hour', {}).get(hour_key, {})
        hour_total = hour_stats.get('total', 0)

        if hour_total >= 5:
            h_wr = hour_stats.get('win_rate', 0.5)
            score_components.append(h_wr)
            if h_wr >= 0.60:
                reasons.append(f"✅ Hora {hour_utc}h UTC favorable: {h_wr*100:.1f}% WR")
            elif h_wr <= 0.40:
                reasons.append(f"⚠️ Hora {hour_utc}h UTC desfavorable: {h_wr*100:.1f}% WR")
        else:
            score_components.append(0.50)

        # ── 3. Calibración de confianza ──────────────────────────────────
        # Si el modelo dice X%, ¿realmente acierta ese %?
        calib = sym_stats.get('confidence_calibration', {})
        # Buscar el bucket más cercano (en pasos de 0.05)
        bucket = round(confidence / 0.05) * 0.05
        bucket_key = f"{bucket:.2f}"
        if bucket_key in calib and calib[bucket_key].get('total', 0) >= 3:
            cal_wr = calib[bucket_key]['win_rate']
            score_components.append(cal_wr)
            reasons.append(
                f"📊 Calibración confianza {confidence*100:.0f}%: "
                f"WR real {cal_wr*100:.1f}%"
            )
        else:
            # Sin calibración: usar confianza directa (penalizar si < 0.45)
            cal_score = min(confidence * 1.1, 1.0) if confidence >= 0.45 else confidence * 0.8
            score_components.append(cal_score)

        # ── 4. Racha de pérdidas recientes ───────────────────────────────
        if recent_trades:
            recent_sym = [t for t in recent_trades if t.get('symbol') == symbol][-5:]
            if recent_sym:
                losses = sum(1 for t in recent_sym if float(t.get('pnl_usdt', 0)) < 0)
                streak_penalty = max(0, (losses - 1) * 0.08)  # -8% por cada pérdida extra
                streak_score = max(0.0, 0.55 - streak_penalty)
                score_components.append(streak_score)
                if losses >= 3:
                    reasons.append(f"🔴 Racha reciente: {losses}/5 pérdidas en {symbol}")
                elif losses == 0 and len(recent_sym) >= 3:
                    reasons.append(f"🟢 Racha positiva: {len(recent_sym)} trades sin pérdidas")

        # ── 5. Confianza base del modelo principal ───────────────────────
        # Siempre incluir como componente con peso moderado
        score_components.append(min(confidence * 1.2, 1.0))

        # ── Calcular meta_score final ────────────────────────────────────
        if score_components:
            meta_score = sum(score_components) / len(score_components)
        else:
            meta_score = confidence

        meta_score = round(max(0.0, min(1.0, meta_score)), 4)

        # ── Umbral dinámico por activo ───────────────────────────────────
        # Activos con bajo WR histórico necesitan mayor convicción del modelo.
        # Fórmula: threshold sube 0.40 puntos por cada 1.0 de WR por debajo del 50%.
        # Ejemplo: POL 25% WR → threshold = 0.52 + (0.50 - 0.25) * 0.40 = 0.62
        # Ejemplo: ETH 58% WR → threshold = 0.52 (WR > 50%, no sube)
        # Cap máximo en 0.72 para no bloquear completamente un activo.
        if total >= MIN_TRADES_FOR_STATS:
            asset_wr = sym_stats.get('win_rate', 0.5)
            dynamic_threshold = META_SCORE_THRESHOLD + max(0.0, (0.50 - asset_wr) * 0.40)
        else:
            asset_wr = 0.5
            dynamic_threshold = META_SCORE_THRESHOLD

        # Penalty temporal por ventana horaria destructiva (14-17 UTC).
        # Se activa desde _autonomous_decide() cuando la hora es riesgosa.
        # Desaparece solo cuando by_hour acumula >= 5 trades y el componente 2
        # del MetaEvaluador ya penaliza esa franja por WR real.
        dynamic_threshold = round(min(dynamic_threshold + window_penalty, 0.75), 4)

        approved = meta_score >= dynamic_threshold

        if dynamic_threshold != META_SCORE_THRESHOLD:
            label = f"WR {asset_wr*100:.1f}%"
            if window_penalty > 0:
                label += f" + ventana riesgosa +{window_penalty:.2f}"
            reasons.append(
                f"📐 Umbral ajustado {symbol}: {dynamic_threshold:.2f} "
                f"({label})"
            )

        if approved:
            reasons.append(
                f"🤖 MetaScore {meta_score:.3f} ≥ umbral {dynamic_threshold:.2f} → APROBADO"
            )
        else:
            reasons.append(
                f"🤖 MetaScore {meta_score:.3f} < umbral {dynamic_threshold:.2f} → RECHAZADO"
            )

        return meta_score, approved, reasons
