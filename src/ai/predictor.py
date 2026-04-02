"""
SysMho — Motor de Predicción (Motor de IA IA).

Carga el modelo XGBoost entrenado e interpreta el flujo de datos
en vivo para dictaminar una de 3 acciones: BUY, SELL o WAIT.
Aplica filtros de inercia, fuerza y convicción táctica.
"""

import os
from typing import Dict, Any, Optional

import joblib
import pandas as pd

from src.constants import (
    NORMAL_MIN_CONFIDENCE,
    AGGRESSIVE_MIN_CONFIDENCE,
    NORMAL_INERTIA_THRESHOLD,
    AGGRESSIVE_INERTIA_THRESHOLD,
    NORMAL_STRENGTH_RATIO,
    AGGRESSIVE_STRENGTH_RATIO,
    HIGH_CONVICTION_THRESHOLD,
    BOUNTY_CONFIDENCE_THRESHOLD,
    BOUNTY_MIN_RR_RATIO,
    BOUNTY_TREND_ALIGNMENT_REQUIRED,
)


class ModelPredictor:
    """Inteligencia Artificial que evalúa las señales de mercado."""

    def __init__(self) -> None:
        """Inicializa el predictor cargando el modelo en memoria."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(base_dir, 'models', 'xgboost_v1.joblib')
        self.model = None
        self.features: Optional[list] = None
        self._load_model()

    def _load_model(self) -> None:
        """Carga el modelo XGBoost previamente entrenado."""
        if not os.path.exists(self.model_path):
            print(f"⚠️ Atención: Motor de IA no encontrado en {self.model_path}.")
            return

        try:
            self.model, self.features = joblib.load(self.model_path)
            print("👁️ Motor de IA (XGBoost) cargado y listo para predecir.")
        except Exception as e:
            print(f"❌ Error crítico al despertar la IA: {e}")

    def predict_signal(
        self, current_data: pd.DataFrame, aggressive: bool = False
    ) -> Dict[str, Any]:
        """
        Recibe lectura del mercado y dictamina acción.

        Args:
            current_data: DataFrame con la última vela y sus features.
            aggressive: Si es True, reduce umbrales para buscar entradas.

        Returns:
            Dict con 'signal_int', 'signal_str', 'confidence',
            'raw_probs', y 'signal_type'.
        """
        if self.model is None or self.features is None:
            return {
                'signal_int': 0, 'signal_str': 'WAIT',
                'confidence': 0.0, 'raw_probs': []
            }

        X = current_data[self.features].iloc[[-1]]

        # Probabilidades: [ SELL, WAIT, BUY ]
        probs = self.model.predict_proba(X)[0]

        prob_sell = probs[0]
        prob_wait = probs[1]
        prob_buy = probs[2]

        # Umbrales según el modo (Normal vs Modo Agresivo)
        min_conf = (AGGRESSIVE_MIN_CONFIDENCE if aggressive 
                    else NORMAL_MIN_CONFIDENCE)
        inertia_th = (AGGRESSIVE_INERTIA_THRESHOLD if aggressive 
                      else NORMAL_INERTIA_THRESHOLD)
        target_ratio = (AGGRESSIVE_STRENGTH_RATIO if aggressive 
                        else NORMAL_STRENGTH_RATIO)

        # 1. Filtro de Inercia (Veto)
        if prob_wait > inertia_th:
            return {
                'signal_int': 0, 'signal_str': 'WAIT',
                'confidence': float(prob_wait),
                'raw_probs': probs.tolist(),
                'reason': f'Mercado Inerte (Veto {int(inertia_th*100)}%)'
            }

        # 2. Selección de clase dominante
        if prob_buy >= prob_sell:
            pred_class = 2
            opp_class = 0
            signal_str = 'BUY'
            signal_int = 1
        else:
            pred_class = 0
            opp_class = 2
            signal_str = 'SELL'
            signal_int = -1

        # 3. Ratio de Fuerza Matemática
        opp_prob = probs[opp_class] if probs[opp_class] > 0 else 0.01
        strength_ratio = probs[pred_class] / opp_prob

        # DECISIÓN TÁCTICA:
        is_impulse = (probs[pred_class] >= min_conf) and \
                     (strength_ratio >= target_ratio)
        is_high_conviction = probs[pred_class] >= HIGH_CONVICTION_THRESHOLD

        if is_high_conviction:
            signal_type = "PREMIUM"
        elif aggressive and is_impulse:
            signal_type = "AGGRESSIVE"
        else:
            signal_type = "STANDARD"

        if not (is_impulse or is_high_conviction):
            return {
                'signal_int': 0, 'signal_str': 'WAIT',
                'confidence': float(probs[pred_class]),
                'raw_probs': probs.tolist(),
                'reason': 'Falta de Impulso (Ratio/Conf)'
            }

        return {
            'signal_int': signal_int,
            'signal_str': signal_str,
            'confidence': float(probs[pred_class]),
            'raw_probs': probs.tolist(),
            'signal_type': signal_type
        }

    def compute_score(
        self,
        prediction: Dict[str, Any],
        trend_5m: str,
        trend_1h: str,
        trend_4h: str,
        rr_ratio: float = 1.0,
    ) -> float:
        """
        Score compuesto para ranking de señales (0.0 – 1.0).

        Pondera confianza (40%), ratio de fuerza (30%),
        alineación de tendencias (20%) y ratio R/R (10%).
        """
        if prediction.get('signal_int', 0) == 0:
            return 0.0

        signal_int = prediction['signal_int']
        raw_probs = prediction.get('raw_probs', [0.0, 1.0, 0.0])
        confidence = float(prediction.get('confidence', 0.0))

        if signal_int == 1:  # BUY
            strength_ratio = raw_probs[2] / max(raw_probs[0], 0.01)
        else:  # SELL
            strength_ratio = raw_probs[0] / max(raw_probs[2], 0.01)

        strength_norm = min(strength_ratio / 5.0, 1.0)

        direction = 'UP' if signal_int == 1 else 'DOWN'
        alignment = sum([
            trend_5m == direction,
            trend_1h == direction,
            trend_4h == direction,
        ]) / 3.0

        rr_norm = min(rr_ratio / 5.0, 1.0)

        score = (
            confidence    * 0.40 +
            strength_norm * 0.30 +
            alignment     * 0.20 +
            rr_norm       * 0.10
        )
        return round(min(score, 1.0), 6)

    def is_bounty(
        self,
        prediction: Dict[str, Any],
        trend_5m: str,
        trend_1h: str,
        trend_4h: str,
        rr_ratio: float = 0.0,
    ) -> bool:
        """
        Retorna True si la señal cumple todos los criterios BOUNTY:
        confianza >= 55%, todas las tendencias alineadas y R/R >= 3.
        """
        if prediction.get('signal_int', 0) == 0:
            return False

        confidence = float(prediction.get('confidence', 0.0))
        signal_int = prediction['signal_int']
        direction = 'UP' if signal_int == 1 else 'DOWN'

        trends_aligned = sum([
            trend_5m == direction,
            trend_1h == direction,
            trend_4h == direction,
        ]) >= BOUNTY_TREND_ALIGNMENT_REQUIRED

        return (
            confidence >= BOUNTY_CONFIDENCE_THRESHOLD
            and trends_aligned
            and rr_ratio >= BOUNTY_MIN_RR_RATIO
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Extrae el peso matemático de cada indicador.

        Returns:
            Dict de features y sus pesos ordenados de forma descendente.
        """
        if self.model is None or self.features is None:
            return {}

        try:
            importances = self.model.feature_importances_
            feat_imp = {
                self.features[i]: float(importances[i])
                for i in range(len(self.features))
            }
            # Ordenar por importancia desc
            return dict(
                sorted(feat_imp.items(), key=lambda item: item[1], reverse=True)
            )
        except Exception as e:
            print(f"⚠️ No se pudo extraer la importancia: {e}")
            return {}
