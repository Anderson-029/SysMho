"""
SysMho — Entrenador Secuencial (Incremental Learning).

Entrena a la IA recorriendo una lista de activos uno por uno.
Carga el modelo en memoria, asimila los patrones de la moneda actual,
lo guarda y pasa a la siguiente limpiando la memoria RAM.
"""

import asyncio
import functools
import gc
import os
from typing import List, Union

import joblib
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.utils.class_weight import compute_sample_weight

from src.ai.trainers.base import BaseTrainer
from src.constants import MODEL_FEATURES


class SequentialTrainer(BaseTrainer):
    """Clase para Entrenamiento Secuencial Multi-Activo."""

    async def train_model(
        self, symbols: Union[str, List[str]], timeframe: str, 
        best_params: dict
    ) -> None:
        """
        Entrena el modelo XGBoost de manera incremental.

        Args:
            symbols: Un símbolo o lista de símbolos a entrenar.
            timeframe: Temporalidad de los datos.
            best_params: Hiperparámetros a usar en el XGBoost.
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        print(
            f"🧠 Iniciando entrenamiento SECUENCIAL (Ataque Serial) para "
            f"{len(symbols)} activos ({timeframe})..."
        )

        model = None
        features = MODEL_FEATURES  # Lista fija de 27 features auditadas

        for i, symbol in enumerate(symbols):
            print(f"\n🚀 [{i+1}/{len(symbols)}] Procesando {symbol}...")

            # 1. Cargar datos
            df_symbol = await self.engineer.get_master_dataframe(
                symbol, timeframe
            )
            if len(df_symbol) < 1000:
                print(f"⚠️ Datos insuficientes para {symbol}. Saltando...")
                continue

            # 2. Etiquetar (usa LABEL_THRESHOLD desde constants)
            df_symbol = self.create_labels(df_symbol)

            # 3. Verificar que todas las features del whitelist existen
            missing = [f for f in features if f not in df_symbol.columns]
            if missing:
                print(f"   ⚠️ Features faltantes para {symbol}: {missing}. Saltando...")
                continue

            X = df_symbol[features]
            y = df_symbol['target']

            dist = y.value_counts().sort_index()
            print(
                f"   📊 Features: {len(features)} | Filas: {len(X)} | "
                f"Dist: SELL={dist.get(0,0)} WAIT={dist.get(1,0)} BUY={dist.get(2,0)}"
            )

            # 4. Cargar modelo previo (de iteración anterior o disco)
            if model is None:
                if os.path.exists(self.model_path):
                    try:
                        print("♻️ Cargando conocimiento previo...")
                        model, loaded_features = joblib.load(self.model_path)
                        if loaded_features != features:
                            print(
                                "⚠️ Desajuste de variables detectado. "
                                "Iniciando modelo desde cero con nuevas features..."
                            )
                            model = xgb.XGBClassifier(**best_params)
                    except Exception as e:
                        print(f"⚠️ Error cargando modelo: {e}")
                        model = xgb.XGBClassifier(**best_params)
                else:
                    model = xgb.XGBClassifier(**best_params)

            # 5. Validación cruzada temporal (TimeSeriesSplit 5 folds)
            # Respeta el orden cronológico — nunca entrena con datos futuros.
            # Usa un modelo temporal por fold para obtener métrica de calidad.
            print(f"   🔬 Validación cruzada temporal (5 folds)...")
            tscv = TimeSeriesSplit(n_splits=5)
            fold_scores = []
            loop = asyncio.get_event_loop()

            for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
                X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
                y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]

                # Pesos de clase balanceados (compensa 85% WAIT → ~33% cada clase)
                weights_fold = compute_sample_weight('balanced', y_tr)

                temp_model = xgb.XGBClassifier(**best_params)
                await loop.run_in_executor(
                    None,
                    functools.partial(temp_model.fit, X_tr, y_tr, sample_weight=weights_fold)
                )

                fold_acc = float(accuracy_score(y_te, temp_model.predict(X_te)))
                fold_scores.append(fold_acc)
                print(f"      Fold {fold}/5 → {fold_acc*100:.2f}%")

            cv_accuracy = float(np.mean(fold_scores))
            cv_std = float(np.std(fold_scores))
            print(f"   🎯 Precisión CV: {cv_accuracy*100:.2f}% ± {cv_std*100:.2f}%")

            # 6. Entrenamiento incremental sobre TODOS los datos del activo
            # (maximiza el conocimiento absorbido por el modelo acumulado)
            print(f"   🧠 Asimilando todos los patrones de {symbol}...")
            weights_full = compute_sample_weight('balanced', y)

            xgb_model_param = None
            try:
                xgb_model_param = model.get_booster()
            except (xgb.core.XGBoostError, Exception):
                xgb_model_param = None

            await loop.run_in_executor(
                None,
                functools.partial(
                    model.fit, X, y,
                    sample_weight=weights_full,
                    xgb_model=xgb_model_param
                )
            )

            # 7. Evaluación final en el último 15% cronológico
            split_idx = int(len(X) * 0.85)
            X_test_final = X.iloc[split_idx:]
            y_test_final = y.iloc[split_idx:]
            y_pred_final = model.predict(X_test_final)
            acc_final = float(accuracy_score(y_test_final, y_pred_final))
            print(f"   📈 Precisión final (15% hold-out): {acc_final*100:.2f}%")

            # 8. Guardar progreso tras cada activo
            joblib.dump((model, features), self.model_path)
            print(f"   💾 Conocimiento consolidado: {self.model_path}")

            # 9. Persistir métricas per-clase en DB y consola
            model_name = f"serial_{symbol.replace('/', '_')}_v3"
            await self.save_performance(
                model_name, acc_final, y_test_final, y_pred_final
            )

            # 10. Limpieza agresiva de memoria (RAM)
            del X, y, X_test_final, y_test_final, y_pred_final, df_symbol
            del temp_model, fold_scores
            gc.collect()

        print("\n🏆 ¡Súper-Entrenamiento Secuencial Completado con Éxito!")
