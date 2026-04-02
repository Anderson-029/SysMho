"""
SysMho — Optimizador de IA (Tuning Bayesiano).

Utiliza Optuna para encontrar la mejor combinación de hiperparámetros
para el XGBoost, adaptándose a las condiciones actuales del mercado.
"""

import asyncio
import functools
import joblib
import optuna
import xgboost as xgb
from sklearn.metrics import log_loss
from sklearn.model_selection import train_test_split

from src.ai.trainers.base import BaseTrainer
from src.constants import MODEL_FEATURES


class BayesianTuner(BaseTrainer):
    """Clase para optimización Bayesiana de hiperparámetros."""

    def _objective(
        self, trial: optuna.Trial, X_train, y_train, X_test, y_test
    ) -> float:
        """Función objetivo que Optuna intentará minimizar (mlogloss)."""
        param = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float(
                'learning_rate', 0.01, 0.2, log=True
            ),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float(
                'colsample_bytree', 0.5, 1.0
            ),
            'gamma': trial.suggest_float('gamma', 1e-8, 1.0, log=True),
            'random_state': 42,
            'eval_metric': 'mlogloss',
            'n_jobs': -1,
            'tree_method': 'hist'
        }

        model = xgb.XGBClassifier(**param)
        model.fit(X_train, y_train)
        preds = model.predict_proba(X_test)

        # Minimizamos el Log Loss
        return log_loss(y_test, preds)

    async def tune_model(
        self, symbol: str, timeframe: str, n_trials: int = 50
    ) -> dict:
        """
        Ejecuta el estudio y guarda los parámetros óptimos encontrados.

        Args:
            symbol: El activo a usar como perfil base (ej. 'BTC/USDT').
            timeframe: La temporalidad a usar.
            n_trials: Cantidad de variaciones a probar.

        Returns:
            Dict con los mejores hiperparámetros encontrados.
        """
        print(
            f"🎯 Iniciando Overclocking Bayesiano para "
            f"{symbol} ({n_trials} intentos)..."
        )
        df = await self.engineer.get_master_dataframe(symbol, timeframe)
        if len(df) < 2000:
            print(f"⚠️ Datos insuficientes para tuning en {symbol}.")
            return None

        # Etiquetar data
        df = self.create_labels(df)

        missing = [f for f in MODEL_FEATURES if f not in df.columns]
        if missing:
            print(f"⚠️ Features faltantes para tuning: {missing}")
            return None

        X = df[MODEL_FEATURES]
        y = df['target']
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.15, shuffle=False
        )

        # Crear y ejecutar el estudio de Optuna
        # run_in_executor evita bloquear el event loop asyncio durante el tuning
        study = optuna.create_study(direction='minimize')
        objective_fn = lambda trial: self._objective(
            trial, X_train, y_train, X_test, y_test
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(study.optimize, objective_fn, n_trials=n_trials)
        )

        print(f"🏆 Mejores parámetros encontrados: {study.best_params}")

        # Guardar en disco para uso futuro del SequentialTrainer
        joblib.dump(study.best_params, self.best_params_path)

        return study.best_params
