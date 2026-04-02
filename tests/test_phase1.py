"""
SysMho — Tests de Regresión: Fase 1 (Limpieza de Base).

Estos tests validan que todos los cambios de la Fase 1 están correctamente
implementados. Si alguno falla, significa que la Fase 1 está incompleta.
"""

import ast


# ================================================================
# 1. Unificación de MIN_NOTIONAL
# ================================================================

def test_min_notional_unified_in_trader():
    """TradeExecutor.MIN_NOTIONAL_SAFE debe ser igual a constants.MIN_NOTIONAL_USDT."""
    from src.constants import MIN_NOTIONAL_USDT
    from src.executor.trader import TradeExecutor

    assert TradeExecutor.MIN_NOTIONAL_SAFE == MIN_NOTIONAL_USDT, (
        f"TradeExecutor usa {TradeExecutor.MIN_NOTIONAL_SAFE} "
        f"pero constants define {MIN_NOTIONAL_USDT}. Deben ser el mismo valor."
    )


def test_min_notional_unified_in_risk_manager():
    """RiskManager.MIN_NOTIONAL debe ser igual a constants.MIN_NOTIONAL_USDT."""
    from src.constants import MIN_NOTIONAL_USDT
    from src.risk.manager import RiskManager

    assert RiskManager.MIN_NOTIONAL == MIN_NOTIONAL_USDT, (
        f"RiskManager usa {RiskManager.MIN_NOTIONAL} "
        f"pero constants define {MIN_NOTIONAL_USDT}. Deben ser el mismo valor."
    )


# ================================================================
# 2. Propiedad pública api_status en TradeExecutor
# ================================================================

def test_api_status_is_a_property():
    """TradeExecutor debe exponer api_status como @property pública."""
    from src.executor.trader import TradeExecutor

    assert isinstance(TradeExecutor.__dict__.get('api_status'), property), (
        "api_status no es una @property en TradeExecutor. "
        "Agregar: @property def api_status(self) -> str: ..."
    )


def test_api_status_returns_internal_value():
    """api_status debe retornar el valor real de _api_status."""
    from src.executor.trader import TradeExecutor

    t = TradeExecutor.__new__(TradeExecutor)
    for estado in ("UNKNOWN", "ACTIVE", "RECONNECTING", "DISCONNECTED"):
        t._api_status = estado
        assert t.api_status == estado, (
            f"api_status devuelve '{t.api_status}' pero _api_status es '{estado}'"
        )


def test_system_route_uses_public_api_status():
    """La ruta /api/system/status debe usar api_status, no _api_status."""
    with open("src/dashboard/routes/system.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "trader._api_status" not in content, (
        "system.py accede a trader._api_status (atributo privado). "
        "Debe usar trader.api_status (property pública)."
    )
    assert "trader.api_status" in content, (
        "system.py no usa trader.api_status. "
        "Reemplazar trader._api_status por trader.api_status."
    )


# ================================================================
# 3. Validación de API keys en settings.py
# ================================================================

def test_settings_validates_api_keys():
    """settings.py debe validar que las API keys no sean None o vacías."""
    with open("config/settings.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "raise ValueError" in content, (
        "settings.py no lanza ValueError cuando faltan las API keys. "
        "Agregar validación al final del módulo."
    )


# ================================================================
# 4. Banner de versión coherente
# ================================================================

def test_version_banner_matches_constant():
    """El banner en start_sysmho.sh debe mostrar la versión de constants.py."""
    from src.constants import SYSMHO_VERSION

    with open("start_sysmho.sh", "r", encoding="utf-8") as f:
        content = f.read()

    assert f"V{SYSMHO_VERSION}" in content, (
        f"start_sysmho.sh no muestra V{SYSMHO_VERSION}. "
        "Sincronizar el banner con SYSMHO_VERSION en constants.py."
    )


# ================================================================
# 5. Sin prints de DEBUG en producción
# ================================================================

def test_no_debug_prints_in_testing_route():
    """La ruta /api/test no debe tener prints de DEBUG."""
    with open("src/dashboard/routes/testing.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "DEBUG" not in content, (
        "src/dashboard/routes/testing.py contiene prints de DEBUG. "
        "Eliminarlos antes de pasar a producción."
    )


# ================================================================
# 6. Sin importaciones duplicadas
# ================================================================

def test_no_duplicate_imports_in_features():
    """features.py no debe importar DatabaseRepository más de una vez."""
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "src.database.repository"
        and any(alias.name == "DatabaseRepository" for alias in node.names)
    ]

    assert len(imports) == 1, (
        f"DatabaseRepository importado {len(imports)} veces en features.py. "
        "Debe aparecer exactamente una vez."
    )
