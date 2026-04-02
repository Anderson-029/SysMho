"""
SysMho — Tests de Validación: Fase 7 (Limpieza Final).

Estos tests FALLARÁN hasta que la Fase 7 esté implementada.
"""

import ast
import pytest


# ================================================================
# 1. trader.py — _execute_sandbox_trade() es código muerto
# ================================================================

def test_trader_has_no_execute_sandbox_trade():
    """
    _execute_sandbox_trade() nunca es llamado desde ningún lugar del
    código. Simula una operación pero no la ejecuta en Binance, con
    lo que puede generar registros en DB que no corresponden a
    operaciones reales (confusión contable).

    Fix: eliminar el método completo.
    """
    with open("src/executor/trader.py", "r", encoding="utf-8") as f:
        source = f.read()

    assert "_execute_sandbox_trade" not in source, (
        "trader.py todavía contiene _execute_sandbox_trade(). "
        "Este método nunca se llama y representa un riesgo contable: "
        "podría registrar trades simulados en la DB como si fueran reales. "
        "Fix: eliminar el método completo."
    )


def test_sandbox_trade_not_called_anywhere():
    """
    Verificar también que ningún otro archivo del proyecto llama
    a _execute_sandbox_trade (por si hubiéramos pasado por alto
    alguna referencia antes de eliminarla).
    """
    import os
    src_root = "src"
    for dirpath, _, filenames in os.walk(src_root):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "_execute_sandbox_trade" not in content, (
                f"{fpath} todavía referencia _execute_sandbox_trade(). "
                "Fix: eliminar todas las referencias antes de eliminar el método."
            )


# ================================================================
# 2. verify_coherence.py — Umbral de 0.01 USDT irrealmente estricto
# ================================================================

def test_coherence_individual_threshold_is_realistic():
    """
    La comparación de PnL por posición usa diff < 0.01 USDT.
    En Futures con apalancamiento, la diferencia entre el PnL de
    Binance (mark price en tiempo real) y el PnL guardado en DB
    (último upsert) puede ser de centavos por pura latencia de red.

    Con 0.01 USDT de umbral, casi cualquier posición abierta
    aparece como '❌ ERROR' aunque el sistema sea perfectamente
    coherente, generando falsas alarmas.

    Fix: cambiar el umbral individual a 1.0 USDT.
    """
    with open("tools/verify_coherence.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    # Buscar comparaciones: diff < X donde X es un número literal
    thresholds_found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, ast.Lt) and isinstance(comparator, ast.Constant):
                    if isinstance(comparator.value, (int, float)):
                        thresholds_found.append(comparator.value)

    assert 0.01 not in thresholds_found, (
        f"verify_coherence.py usa 0.01 USDT como umbral de coherencia. "
        f"Umbrales encontrados: {thresholds_found}. "
        "Fix: cambiar 'diff < 0.01' a 'diff < 1.0' para evitar "
        "falsas alarmas por latencia de red."
    )


def test_coherence_global_threshold_is_realistic():
    """
    El umbral global (global_diff < 0.05) tampoco es realista.
    Con 10 posiciones abiertas simultáneas, la suma de diferencias
    de latencia puede superar fácilmente 0.05 USDT.

    Fix: cambiar el umbral global a 1.0 USDT también.
    """
    with open("tools/verify_coherence.py", "r", encoding="utf-8") as f:
        source = f.read()

    assert "0.05" not in source, (
        "verify_coherence.py usa 0.05 USDT como umbral global. "
        "Fix: cambiar 'global_diff < 0.05' a 'global_diff < 1.0'."
    )
