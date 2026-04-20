"""
SysMho — Orquestador de Entrenamiento IA.

Actúa como proxy entre la interfaz principal (`main.py`)
y los submódulos especializados (`SequentialTrainer`, `BayesianTuner`).
Mantiene la misma interfaz original para no romper dependencias.
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import asyncio
import os
from typing import List, Union

import joblib

from src.ai.trainers.sequential import SequentialTrainer
from src.ai.trainers.tuner import BayesianTuner
from src.constants import DEFAULT_MODEL_PARAMS, SYMBOLS, TRAINING_WINDOW_MONTHS


class ModelTrainer:
    """Orquestador que coordina a los entrenadores concretos."""

    def __init__(self, db=None) -> None:
        """Inicializa los submódulos inyectando la dependencia DB."""
        self.sequential = SequentialTrainer(db=db)
        self.tuner = BayesianTuner(db=db)

    async def train_model(
        self, symbols: Union[str, List[str]], timeframe: str,
        tune: bool = False, n_trials: int = 30,
        window_months: int = TRAINING_WINDOW_MONTHS
    ) -> None:
        """
        Orquesta el entrenamiento.
        Si 'tune' es True, corre el Tuner Bayesiano.
        Luego corre el SequentialTrainer.

        Args:
            window_months: Meses de datos a usar (sliding window).
                           Default: TRAINING_WINDOW_MONTHS (3 meses).
        """
        # Parámetros base por defecto si no hay tuning (desde constants.py)
        best_params = {**DEFAULT_MODEL_PARAMS, 'tree_method': 'hist'}

        # Manejo de Optuna (Tuning Bayesiano)
        if tune or os.path.exists(self.tuner.best_params_path):
            try:
                if tune:
                    # Sintonizar usando el primer símbolo como referencia
                    ref_symbol = symbols[0] if isinstance(symbols, list) \
                        else symbols
                    tuned_params = await self.tuner.tune_model(
                        ref_symbol, timeframe, n_trials=n_trials,
                        window_months=window_months
                    )
                    if tuned_params:
                        best_params.update(tuned_params)
                elif os.path.exists(self.tuner.best_params_path):
                    print("♻️ Cargando configuración Bayesiana previa...")
                    saved_params = joblib.load(self.tuner.best_params_path)
                    best_params.update(saved_params)
            except Exception as e:
                print(f"⚠️ Error cargando optimización: {e}. Usando base.")

        # Iniciar Entrenamiento Secuencial con sliding window
        await self.sequential.train_model(
            symbols, timeframe, best_params, window_months=window_months
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Orquestador de Entrenamiento de SysMho'
    )
    parser.add_argument(
        '--symbol', type=str, default='ALL',
        help='Símbolo o ALL para el Portafolio Activo'
    )
    parser.add_argument(
        '--timeframe', type=str, default='5m', help='Temporalidad'
    )
    parser.add_argument(
        '--tune', action='store_true',
        help='Activa el Tuning Bayesiano (Tuning)'
    )
    parser.add_argument(
        '--trials', type=int, default=30,
        help='Número de intentos para tuning'
    )
    parser.add_argument(
        '--window-months', type=int, default=TRAINING_WINDOW_MONTHS,
        help=f'Meses de datos para sliding window (default: {TRAINING_WINDOW_MONTHS})'
    )

    args = parser.parse_args()
    trainer = ModelTrainer()

    target_symbols = SYMBOLS if args.symbol == 'ALL' else [args.symbol]

    try:
        asyncio.run(
            trainer.train_model(
                symbols=target_symbols,
                timeframe=args.timeframe,
                tune=args.tune,
                n_trials=args.trials,
                window_months=args.window_months
            )
        )
    except KeyboardInterrupt:
        print("\nEntrenamiento interrumpido manualmente.")
