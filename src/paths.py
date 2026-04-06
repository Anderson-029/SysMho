"""
SysMho — Centralized Data Directory Paths.

Resolves all IPC, model, and log file paths from a single source.
- Local dev (no Docker): SYSMHO_DATA_DIR unset → defaults to src/ → exact same paths as before.
- Docker: SYSMHO_DATA_DIR=/app/data → all files on the shared volume.
"""

import os

_default = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get('SYSMHO_DATA_DIR', _default)

RUNTIME_STATE = os.path.join(DATA_DIR, 'runtime_state.json')
BRAIN_LOG = os.path.join(DATA_DIR, 'sysmho_brain.log')
MODELS_DIR = os.path.join(DATA_DIR, 'ai', 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'xgboost_v1_1.joblib')
BEST_PARAMS_PATH = os.path.join(MODELS_DIR, 'best_params.joblib')
META_STATS_PATH = os.path.join(MODELS_DIR, 'meta_stats.json')
ENGINE_HEARTBEAT = os.path.join(DATA_DIR, 'engine_heartbeat')
