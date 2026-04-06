"""
SysMho — Tests de Validación: Fase 3 (Bugs Críticos de Lógica).

Estos tests FALLARÁN hasta que la Fase 3 esté implementada.
Cada uno define exactamente qué debe cambiar y por qué.
"""

import ast
import pytest


# ================================================================
# 1. monitor.py — NameError: qty y entry_price fuera de scope
# ================================================================

def test_monitor_qty_defined_before_if_official():
    """
    qty y entry_price deben definirse ANTES del bloque 'if official:'
    en _check_position. Si solo están en el else, hay NameError cuando
    Binance sí tiene datos oficiales para la posición.
    """
    with open("src/executor/monitor.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name == '_check_position'):
            continue

        qty_line = None
        official_if_line = None

        for stmt in ast.walk(node):
            # Buscar asignación de qty (no dentro de else)
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == 'qty':
                        # Solo registrar la primera aparición
                        if qty_line is None:
                            qty_line = stmt.lineno

            # Buscar "if official:"
            if isinstance(stmt, ast.If):
                if isinstance(stmt.test, ast.Name) and stmt.test.id == 'official':
                    if official_if_line is None:
                        official_if_line = stmt.lineno

        assert qty_line is not None, "qty no está definida en _check_position"
        assert official_if_line is not None, "'if official:' no encontrado"
        assert qty_line < official_if_line, (
            f"qty (línea {qty_line}) debe definirse ANTES de 'if official:' "
            f"(línea {official_if_line}). "
            "Actualmente el código lanza NameError cuando Binance tiene datos."
        )
        return

    pytest.fail("_check_position no encontrada en monitor.py")


# ================================================================
# 2. trainer.py — args.trials nunca se pasa a tune_model
# ================================================================

def test_trainer_passes_trials_argument():
    """
    El CLI de trainer.py parsea --trials pero nunca lo pasa a tune_model.
    Después del fix, n_trials=args.trials debe aparecer en la llamada.
    """
    with open("src/ai/trainer.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "n_trials=args.trials" in content, (
        "args.trials se parsea con argparse pero nunca se pasa a train_model. "
        "Agregar n_trials=args.trials en la llamada y el parámetro en train_model."
    )


def test_train_model_accepts_n_trials_param():
    """
    train_model debe aceptar el parámetro n_trials y pasarlo a tune_model.
    """
    with open("src/ai/trainer.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'train_model':
            param_names = [arg.arg for arg in node.args.args]
            assert 'n_trials' in param_names, (
                f"train_model no tiene el parámetro n_trials. "
                f"Parámetros actuales: {param_names}"
            )
            return

    pytest.fail("train_model no encontrada en trainer.py")


# ================================================================
# 3. portfolio.py — adjust_capital resetea in_positions a 0
# ================================================================

def test_adjust_capital_does_not_hardcode_in_positions_zero():
    """
    adjust_portfolio_capital no debe resetear in_positions a 0 sin consultar
    la tabla positions. Si hay posiciones abiertas, el capital queda incorrecto.
    Verifica que la función lea el valor real desde la tabla positions.
    """
    with open("src/dashboard/routes/portfolio.py", "r", encoding="utf-8") as f:
        content = f.read()

    # La función corregida debe consultar la tabla positions y usar un parámetro ($2)
    # en lugar de hardcodear 0. Buscamos las dos marcas del fix.
    assert "SUM(invested_usdt)" in content, (
        "adjust_portfolio_capital no consulta SUM(invested_usdt) FROM positions. "
        "Debe leer el capital real en posiciones antes de actualizar el portafolio."
    )
    assert "in_positions" in content and "$2" in content, (
        "adjust_portfolio_capital debe usar in_positions = $2 (valor real desde BD), "
        "no in_positions = 0.0 hardcodeado."
    )


# ================================================================
# 4. risk/manager.py — db.connect() dentro de lógica de negocio
# ================================================================

def test_risk_manager_no_db_connect_in_business_logic():
    """
    evaluate_signal y _log_to_db no deben llamar self.db.connect().
    La conexión pertenece al ciclo de arranque del sistema, no a cada evaluación.
    """
    with open("src/risk/manager.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    business_methods = {'evaluate_signal', '_log_to_db'}

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name in business_methods):
            continue

        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                if (isinstance(inner.func, ast.Attribute) and
                        inner.func.attr == 'connect'):
                    pytest.fail(
                        f"'{node.name}' llama a db.connect() en lógica de negocio "
                        f"(línea {inner.lineno}). "
                        "La conexión debe establecerse en el arranque, no en cada ciclo."
                    )


# ================================================================
# 5. stop_sysmho.sh — apagado sin verificar posiciones abiertas
# ================================================================

def test_stop_script_checks_open_positions():
    """
    La documentación debe recordar el riesgo de posiciones abiertas al detener el motor
    (antes: stop_sysmho.sh; ahora: README / operación manual con uv).
    """
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read().lower()

    assert "positions" in content or "posiciones" in content, (
        "README.md debe mencionar posiciones (abiertas / gestión) al documentar apagado o riesgo."
    )


def test_stop_script_version_is_current():
    """README debe reflejar la versión actual (sustituye banner de stop_sysmho.sh)."""
    from src.constants import SYSMHO_VERSION

    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    assert f"v{SYSMHO_VERSION}".lower() in content.lower(), (
        f"README.md no muestra v{SYSMHO_VERSION}. Sincronizar con SYSMHO_VERSION en constants.py."
    )
