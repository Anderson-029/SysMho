"""
SysMho — Configuración en Tiempo de Ejecución (canal compartido).

Permite que el dashboard y el motor de IA lean/escriban configuración
sin necesidad de reiniciar ningún proceso.

El archivo runtime_state.json actúa como canal de comunicación entre:
  - src/dashboard (FastAPI, proceso 1)  → escribe
  - src/main.py   (engine, proceso 2)   → lee

Si el archivo no existe o está corrupto, se usan los valores de .env.
"""

import json
import os

from src.paths import RUNTIME_STATE as _STATE_PATH


def _load() -> dict:
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(state: dict) -> None:
    tmp = _STATE_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, _STATE_PATH)


def is_autonomous() -> bool:
    """Lee el modo autónomo desde runtime_state.json (fallback: .env)."""
    state = _load()
    if 'autonomous_mode' in state:
        return bool(state['autonomous_mode'])
    # Fallback al .env si nunca se escribió el estado
    return os.getenv('AUTONOMOUS_MODE', 'false').lower() == 'true'


def set_autonomous(enable: bool) -> None:
    """Escribe el modo autónomo en runtime_state.json."""
    state = _load()
    state['autonomous_mode'] = enable
    _save(state)


def reset_daily_pnl() -> str:
    """
    Marca el momento de reset del PnL diario.

    get_stats() calculará PnL solo desde este timestamp en adelante,
    lo que efectivamente pone el contador en cero sin borrar trades reales.

    Returns: timestamp ISO del reset.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    state = _load()
    state['pnl_reset_at'] = now_iso
    _save(state)
    return now_iso


def get_pnl_reset_at() -> str:
    """Devuelve el timestamp del último reset de PnL, o None."""
    return _load().get('pnl_reset_at')


def reset_circuit_breaker() -> str:
    """
    Marca el momento del reset del Circuit Breaker.

    get_daily_stats() filtrará solo trades posteriores a este timestamp,
    efectivamente reiniciando los contadores del CB sin borrar datos reales.

    Returns: timestamp ISO del reset.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    state = _load()
    state['cb_reset_at'] = now_iso
    _save(state)
    return now_iso


def get_cb_reset_at() -> str:
    """Devuelve el timestamp del último reset del CB, o None si no hay."""
    return _load().get('cb_reset_at')


def set_sync_status(status: str, detail: str = '') -> None:
    """
    Escribe el estado de sincronización de datos.
    status: 'syncing' | 'done' | 'idle'
    """
    state = _load()
    state['sync_status'] = status
    state['sync_detail'] = detail
    _save(state)


def get_sync_status() -> dict:
    state = _load()
    return {
        'status': state.get('sync_status', 'idle'),
        'detail': state.get('sync_detail', ''),
    }


def set_last_scan_at() -> str:
    """
    Registra el timestamp del último scan de 5 minutos.

    Se escribe al inicio de cada ciclo, independientemente de si el
    scan produce señales o todos los activos quedan en WAIT.
    Permite que el frontend sincronice el cronómetro correctamente.

    Returns: timestamp ISO del scan.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    state = _load()
    state['last_scan_at'] = now_iso
    _save(state)
    return now_iso


def get_last_scan_at() -> str:
    """Devuelve el timestamp del último scan de 5 minutos, o None."""
    return _load().get('last_scan_at')


def get_state() -> dict:
    """Devuelve todo el estado runtime."""
    return _load()
