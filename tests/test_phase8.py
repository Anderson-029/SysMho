"""
test_phase8.py — Coherencia BD vs Binance

Verifica que los cuatro bugs críticos de desincronización entre la BD local
y Binance están correctamente corregidos en el código fuente.
"""

import ast


def test_monitor_detects_side_mismatch():
    """_check_position compara official['side'] con pos['side'] antes de usar los datos."""
    source = open("src/executor/monitor.py", encoding="utf-8").read()
    assert "official['side']" in source, "monitor.py debe comparar official['side']"
    assert "pos['side']" in source, "monitor.py debe comparar pos['side']"


def test_monitor_has_correct_side_mismatch_method():
    """PositionMonitor tiene el método _correct_side_mismatch."""
    source = open("src/executor/monitor.py", encoding="utf-8").read()
    assert "_correct_side_mismatch" in source, (
        "monitor.py debe tener el método _correct_side_mismatch "
        "para corregir posiciones con lado invertido"
    )


def test_monitor_side_mismatch_check_before_price_use():
    """La verificación de side mismatch ocurre ANTES de usar current_price y pnl_unrealized."""
    source = open("src/executor/monitor.py", encoding="utf-8").read()
    idx_mismatch = source.find("_correct_side_mismatch")
    idx_current_price = source.find("current_price = official['mark_price']")
    assert idx_mismatch < idx_current_price, (
        "El check de SIDE_MISMATCH debe aparecer antes de asignar current_price"
    )


def test_reduce_only_error_returns_false():
    """El error -2022 / ReduceOnly retorna False en close_position_on_exchange."""
    source = open("src/executor/trader.py", encoding="utf-8").read()
    idx = source.find("ReduceOnly Order is rejected")
    assert idx != -1, "trader.py debe capturar el error ReduceOnly Order is rejected"
    # El bloque del if puede tener un log largo antes del return — ampliamos ventana
    block = source[idx:idx + 600]
    assert "return False" in block, (
        "Bug -2022 corregido: el error ReduceOnly debe retornar False "
        "para NO limpiar la BD cuando Binance rechaza el cierre"
    )
    assert "return True" not in block, (
        "Bug -2022: el bloque ReduceOnly NO debe retornar True "
        "(esto causaba limpieza de BD sin confirmar cierre real)"
    )


def test_startup_reconciliation_exists_in_main():
    """AutonomousBot tiene el método _startup_reconciliation."""
    source = open("src/main.py", encoding="utf-8").read()
    assert "_startup_reconciliation" in source, (
        "main.py debe tener _startup_reconciliation para reconciliar BD vs Binance al arrancar"
    )


def test_startup_calls_reconciliation_before_gapfiller():
    """start() llama _startup_reconciliation antes del GapFiller."""
    source = open("src/main.py", encoding="utf-8").read()
    idx_reconcile = source.find("await self._startup_reconciliation()")
    idx_gap = source.find("GapFiller(")
    assert idx_reconcile != -1, "start() debe llamar await self._startup_reconciliation()"
    assert idx_gap != -1, "start() debe usar GapFiller"
    assert idx_reconcile < idx_gap, (
        "_startup_reconciliation debe llamarse ANTES del GapFiller en start()"
    )


def test_repository_has_sync_wallet_from_exchange():
    """DatabaseRepository tiene sync_wallet_from_exchange."""
    source = open("src/database/repository.py", encoding="utf-8").read()
    assert "sync_wallet_from_exchange" in source, (
        "repository.py debe tener sync_wallet_from_exchange "
        "para sobrescribir el portfolio con valores reales de Binance"
    )


def test_sync_wallet_uses_update_not_insert():
    """sync_wallet_from_exchange usa UPDATE (no INSERT) para no duplicar filas de portfolio."""
    source = open("src/database/repository.py", encoding="utf-8").read()
    idx = source.find("sync_wallet_from_exchange")
    # El docstring puede ser largo — buscamos en una ventana amplia
    block = source[idx:idx + 900]
    assert "UPDATE portfolio" in block, (
        "sync_wallet_from_exchange debe usar UPDATE para sobrescribir el portfolio existente"
    )
