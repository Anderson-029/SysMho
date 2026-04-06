"""
SysMho — Clase Base de Entrenamiento.

Contiene la lógica compartida: etiquetado de datos y persistencia
de métricas de rendimiento en PostgreSQL.
"""

import os
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, precision_score, recall_score

from src.analysis.features import FeatureEngineer
from src.constants import LABEL_THRESHOLD
from src.database.repository import DatabaseRepository


class BaseTrainer:
    """Clase base con utilidades comunes para entrenar modelos."""

    def __init__(self, db: Optional[DatabaseRepository] = None) -> None:
        """Inicializa el entrenador base."""
        self.db = db if db else DatabaseRepository()
        self.engineer = FeatureEngineer(db=self.db)

        from src.paths import MODEL_PATH, BEST_PARAMS_PATH, MODELS_DIR
        self.model_path = MODEL_PATH
        self.best_params_path = BEST_PARAMS_PATH

        # Crear carpeta de modelos si no existe
        os.makedirs(MODELS_DIR, exist_ok=True)

    def create_labels(
        self, df: pd.DataFrame, threshold: float = LABEL_THRESHOLD
    ) -> pd.DataFrame:
        """
        Calcula el retorno futuro para etiquetar la respuesta correcta.

        Args:
            df: DataFrame con cálculos matemáticos y precio 'close'.
            threshold: Movimiento porcentual mínimo para ser BUY o SELL.

        Returns:
            DataFrame con la nueva columna 'target' para entrenar IA.
        """
        df = df.copy()

        # Retorno de la SIGUIENTE vela (el futuro a predecir)
        df['next_return'] = df['close'].shift(-1) / df['close'] - 1

        # Eliminar la última fila real (no tiene "futuro" aún)
        df.dropna(subset=['next_return'], inplace=True)

        # Etiquetado duro: 1 (Comprar), -1 (Vender), 0 (Esperar)
        conditions = [
            (df['next_return'] > threshold),
            (df['next_return'] < -threshold)
        ]
        choices = [1, -1]
        df['target'] = np.select(conditions, choices, default=0)

        # Mapeamos algebraicamente para XGBoost Multi-Class:
        # -1 -> 0 (Vender), 0 -> 1 (Esperar), 1 -> 2 (Comprar)
        df['target'] = df['target'] + 1

        return df

    async def save_performance(
        self, model_name: str, accuracy: float, y_test: pd.Series,
        y_pred: np.ndarray
    ) -> None:
        """
        Calcula y guarda métricas extendidas en la base de datos.
        Imprime métricas per-clase (SELL/WAIT/BUY) para diagnóstico.

        Args:
            model_name: Identificador del modelo (ej. 'serial_BTC_USDT_v2').
            accuracy: Precisión global calculada previamente.
            y_test: Serie real de pruebas.
            y_pred: Array de predicciones hechas por la IA.
        """
        precision = float(
            precision_score(y_test, y_pred, average='weighted', zero_division=0)
        )
        recall = float(
            recall_score(y_test, y_pred, average='weighted', zero_division=0)
        )
        total = len(y_test)
        correct = int(np.sum(y_pred == y_test))

        # Métricas per-clase para diagnóstico de calidad del modelo
        # Clases: 0=SELL, 1=WAIT, 2=BUY (encoding de XGBoost)
        present_classes = sorted(np.unique(np.concatenate([y_test, y_pred])))
        label_names = {0: 'SELL', 1: 'WAIT', 2: 'BUY'}
        target_names = [label_names[c] for c in present_classes]

        report = classification_report(
            y_test, y_pred,
            labels=present_classes,
            target_names=target_names,
            zero_division=0
        )
        print(f"\n   📊 Métricas por Clase ({model_name}):\n{report}")

        query = '''
            INSERT INTO model_performance
                (model_name, accuracy, precision_score, recall,
                 total_predictions, correct_predictions)
            VALUES ($1, $2, $3, $4, $5, $6)
        '''
        await self.db.connect()
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                query, model_name, accuracy, precision,
                recall, total, correct
            )
