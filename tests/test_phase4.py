"""
SysMho — Tests de Validación: Fase 4 (Concurrencia y Event Loop).

Estos tests FALLARÁN hasta que la Fase 4 esté implementada.
Cada uno define exactamente qué debe cambiar y por qué.
"""

import ast
import pytest


# ================================================================
# 1. sequential.py — model.fit() bloquea el event loop
# ================================================================

def test_sequential_trainer_uses_run_in_executor_for_fit():
    """
    model.fit() es síncrono y bloquea el event loop asyncio mientras entrena.
    Todos los WebSockets se congelan durante el entrenamiento.
    Fix: ejecutar model.fit en run_in_executor.
    """
    with open("src/ai/trainers/sequential.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "run_in_executor" in content, (
        "sequential.py llama a model.fit() directamente en el event loop. "
        "Bloquea todos los WebSockets durante el entrenamiento. "
        "Fix: loop = asyncio.get_event_loop(); "
        "await loop.run_in_executor(None, functools.partial(model.fit, X_train, y_train, ...))"
    )


def test_sequential_trainer_fit_not_called_directly():
    """
    model.fit() no debe llamarse como expresión directa en train_model.
    Debe estar envuelto en run_in_executor para no bloquear el event loop.
    """
    with open("src/ai/trainers/sequential.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == 'train_model'):
            continue

        for inner in ast.walk(node):
            # Buscar llamadas directas a .fit() como expresión autónoma (no anidada en await/assign)
            if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Call):
                call = inner.value
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'fit'):
                    pytest.fail(
                        f"model.fit() llamado directamente como expresión en línea {inner.lineno}. "
                        "Bloquea el event loop asyncio durante el entrenamiento. "
                        "Fix: await loop.run_in_executor(None, functools.partial(model.fit, ...))"
                    )
        return

    pytest.fail("train_model no encontrada en sequential.py")


# ================================================================
# 2. tuner.py — study.optimize() bloquea el event loop
# ================================================================

def test_tuner_uses_run_in_executor_for_optimize():
    """
    study.optimize() de Optuna es síncrono y bloquea el event loop.
    Durante el tuning Bayesiano (decenas de trials), todos los WebSockets se congelan.
    Fix: ejecutar study.optimize en run_in_executor.
    """
    with open("src/ai/trainers/tuner.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "run_in_executor" in content, (
        "tuner.py llama a study.optimize() directamente en el event loop. "
        "Bloquea todos los WebSockets mientras Optuna ejecuta sus trials. "
        "Fix: loop = asyncio.get_event_loop(); "
        "await loop.run_in_executor(None, functools.partial(study.optimize, ...))"
    )


def test_tuner_optimize_not_called_directly():
    """
    study.optimize() no debe llamarse como expresión directa en tune_model.
    Debe estar envuelto en run_in_executor para no bloquear el event loop.
    """
    with open("src/ai/trainers/tuner.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == 'tune_model'):
            continue

        for inner in ast.walk(node):
            if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Call):
                call = inner.value
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'optimize'):
                    pytest.fail(
                        f"study.optimize() llamado directamente como expresión en línea {inner.lineno}. "
                        "Bloquea el event loop asyncio durante el tuning Bayesiano. "
                        "Fix: await loop.run_in_executor(None, functools.partial(study.optimize, ...))"
                    )
        return

    pytest.fail("tune_model no encontrada en tuner.py")


# ================================================================
# 3. websocket.py — 30 tasks duplicadas de sentiment y order book
# ================================================================

def test_websocket_sentiment_not_launched_unconditionally_in_watch_ohlcv():
    """
    watch_ohlcv() se llama 3 veces por símbolo (5m, 1h, 4h).
    _keep_sentiment_alive y _monitor_order_book NO deben lanzarse en cada llamada.
    Para 10 símbolos × 3 timeframes = 30 tasks duplicadas de cada servicio.
    Fix: guardar en un set los símbolos que ya tienen estas tasks corriendo.
    """
    with open("src/collector/websocket.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == 'watch_ohlcv'):
            continue

        # Recorrer solo el cuerpo directo de watch_ohlcv (no recursivo)
        # para detectar create_task incondicionales (no dentro de un if)
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'create_task'):
                    if call.args:
                        arg = call.args[0]
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
                            method = arg.func.attr
                            if method in ('_keep_sentiment_alive', '_monitor_order_book'):
                                pytest.fail(
                                    f"create_task({method}) llamado incondicionalmente "
                                    f"en watch_ohlcv (línea {stmt.lineno}). "
                                    "watch_ohlcv se llama 3 veces por símbolo → "
                                    "30 tasks duplicadas para 10 símbolos. "
                                    "Fix: usar self._started_symbols para lanzarlas solo una vez."
                                )
        return

    pytest.fail("watch_ohlcv no encontrada en websocket.py")


def test_websocket_has_guard_set_for_symbol_tasks():
    """
    BinanceWebSocket debe tener un set de control para evitar
    lanzar tasks duplicadas de sentiment y order book por símbolo.
    """
    with open("src/collector/websocket.py", "r", encoding="utf-8") as f:
        content = f.read()

    has_guard = (
        "_started_symbols" in content or
        "_running_symbols" in content or
        "_active_symbols" in content or
        "_sentiment_started" in content
    )

    assert has_guard, (
        "BinanceWebSocket no tiene ningún set de control para evitar tasks duplicadas. "
        "Fix: añadir self._started_symbols = set() en __init__ "
        "y un guard 'if symbol not in self._started_symbols:' en watch_ohlcv."
    )


# ================================================================
# 4. features.py — 10 queries por ciclo en _calculate_historical_swarm
# ================================================================

def test_swarm_uses_single_query_with_any():
    """
    _calculate_historical_swarm() hace una query DB por símbolo en un for loop.
    Para 10 símbolos = 10 queries por cada ciclo de análisis (cada 30s).
    Fix: una sola query con WHERE symbol = ANY($1).
    """
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "ANY($1)" in content, (
        "_calculate_historical_swarm hace 10 queries separadas (una por símbolo). "
        "Fix: reemplazar el for loop con una sola query: "
        "WHERE symbol = ANY($1) AND timeframe = '5m'"
    )


def test_swarm_does_not_loop_fetch_per_symbol():
    """
    _calculate_historical_swarm no debe llamar _fetch_data dentro de un for loop
    iterando sobre cada símbolo del portafolio.
    """
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name == '_calculate_historical_swarm'):
            continue

        for stmt in ast.walk(node):
            if isinstance(stmt, ast.For):
                for inner in ast.walk(stmt):
                    if (isinstance(inner, ast.Call) and
                            isinstance(inner.func, ast.Attribute) and
                            inner.func.attr == '_fetch_data'):
                        pytest.fail(
                            f"_calculate_historical_swarm llama a _fetch_data dentro "
                            f"de un for loop (línea ~{stmt.lineno}). "
                            "Para 10 símbolos = 10 queries por ciclo de 30s. "
                            "Fix: una sola query con WHERE symbol = ANY($1)."
                        )
        return

    pytest.fail("_calculate_historical_swarm no encontrada en features.py")
