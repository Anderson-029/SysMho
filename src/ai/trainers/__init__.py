"""
SysMho — IA Trainers Package.

Exporta las clases base, de entrenamiento secuencial y de optimización
para el modelo XGBoost central.
"""

from src.ai.trainers.base import BaseTrainer
from src.ai.trainers.sequential import SequentialTrainer
from src.ai.trainers.tuner import BayesianTuner

__all__ = ['BaseTrainer', 'SequentialTrainer', 'BayesianTuner']
