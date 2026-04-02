"""
SysMho — Tests de Validación: Fase 5 (Race Conditions).

Estos tests FALLARÁN hasta que la Fase 5 esté implementada.
Cada uno define exactamente qué debe cambiar y por qué.
"""

import ast
import pytest


# ================================================================
# 1. main.py — Race condition: pending_id no se registra en
#    active_handlers antes de que el scanner lo detecte
# ================================================================

def test_brain_loop_registers_pending_id_before_creating_task():
    """
    _store_signal registra pending_id en active_handlers ANTES de crear la task.

    El _continuous_signal_scanner corre cada 5s y busca pending_approvals
    con status PENDING que no estén en active_handlers. Si _store_signal
    crea la task sin registrar el id, el scanner detecta el mismo pending
    como "huérfano" y lanza una segunda task → riesgo de orden duplicada.

    Implementado en _store_signal (renombrado de _brain_loop).
    """
    with open("src/main.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    # Buscar en _store_signal (renombrada desde _brain_loop)
    target_names = ('_store_signal', '_brain_loop')
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name in target_names):
            continue

        stmts = list(ast.walk(node))

        create_task_lines = []
        add_to_handlers_lines = []

        for stmt in stmts:
            # Buscar asyncio.create_task llamando a _process_signal_task
            # o _handle_pending_approval (ambas son formas válidas del fix)
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'create_task'):
                    if call.args:
                        arg = call.args[0]
                        if (isinstance(arg, ast.Call) and
                                isinstance(arg.func, ast.Attribute) and
                                arg.func.attr in (
                                    '_handle_pending_approval',
                                    '_process_signal_task'
                                )):
                            create_task_lines.append(stmt.lineno)

            # Buscar self.active_handlers.add(pending_id)
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'add' and
                        isinstance(call.func.value, ast.Attribute) and
                        call.func.value.attr == 'active_handlers'):
                    add_to_handlers_lines.append(stmt.lineno)

        assert len(create_task_lines) > 0, (
            "No se encontró asyncio.create_task(_handle_pending_approval) en _brain_loop"
        )
        assert len(add_to_handlers_lines) > 0, (
            "_brain_loop no llama self.active_handlers.add() después de crear la task. "
            "Sin esto, el scanner puede detectar el pending como huérfano y duplicar la orden."
        )

        # El add debe ocurrir ANTES del create_task (línea menor)
        first_add = min(add_to_handlers_lines)
        first_create = min(create_task_lines)

        assert first_add < first_create, (
            f"self.active_handlers.add() está en línea {first_add} pero "
            f"asyncio.create_task() está en línea {first_create}. "
            "El registro debe ocurrir ANTES de crear la task para evitar la race condition."
        )
        return

    pytest.fail("_store_signal (ni _brain_loop) encontrada en main.py")


def test_brain_loop_uses_process_signal_task_wrapper():
    """
    _brain_loop debe delegar a _process_signal_task (que tiene el finally
    para limpiar active_handlers) en lugar de llamar directamente a
    _handle_pending_approval. Esto garantiza que el id se elimina del set
    aunque la task falle.
    """
    with open("src/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # _brain_loop debe crear tasks de _process_signal_task, no de _handle_pending_approval
    # (el scanner ya usa _process_signal_task correctamente)
    assert "_process_signal_task" in content, (
        "_process_signal_task no existe en main.py. "
        "Este wrapper con finally garantiza que active_handlers.discard() "
        "se ejecuta aunque la tarea falle."
    )


# ================================================================
# 2. features.py — El swarm incluye el símbolo que está siendo evaluado
# ================================================================

def test_swarm_excludes_current_symbol():
    """
    _calculate_historical_swarm() promedia RSI/MACD de TODO el portafolio,
    incluyendo el símbolo que está siendo evaluado en ese momento.

    Esto introduce sesgo: el símbolo se evalúa a sí mismo como parte del
    contexto global. El enjambre debe reflejar el comportamiento del RESTO
    del portafolio, no incluirse a sí mismo.

    Fix: añadir parámetro 'exclude_symbol' y filtrarlo en la query.
    """
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name == '_calculate_historical_swarm'):
            continue

        param_names = [arg.arg for arg in node.args.args]
        assert 'exclude_symbol' in param_names, (
            f"_calculate_historical_swarm no tiene parámetro 'exclude_symbol'. "
            f"Parámetros actuales: {param_names}. "
            "Fix: añadir 'exclude_symbol: Optional[str] = None' y filtrarlo en la query."
        )
        return

    pytest.fail("_calculate_historical_swarm no encontrada en features.py")


def test_swarm_filters_excluded_symbol_in_query():
    """
    La query de _calculate_historical_swarm debe excluir el símbolo actual
    cuando se proporciona exclude_symbol.
    """
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "exclude_symbol" in content, (
        "_calculate_historical_swarm no maneja 'exclude_symbol'. "
        "Fix: filtrar el símbolo actual de la lista SYMBOLS antes de la query."
    )


def test_swarm_called_with_current_symbol_in_get_master_dataframe():
    """
    get_master_dataframe debe pasar el símbolo actual a _calculate_historical_swarm
    para que sea excluido del enjambre.
    """
    with open("src/analysis/features.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and
                node.name == 'get_master_dataframe'):
            continue

        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            if not (isinstance(inner.func, ast.Attribute) and
                    inner.func.attr == '_calculate_historical_swarm'):
                continue

            # Verificar que se pasa algún argumento (el exclude_symbol)
            has_exclude_arg = (
                len(inner.args) > 1 or
                any(kw.arg == 'exclude_symbol' for kw in inner.keywords)
            )
            assert has_exclude_arg, (
                "get_master_dataframe llama a _calculate_historical_swarm "
                "sin pasar el símbolo actual como exclude_symbol. "
                "Fix: await self._calculate_historical_swarm(limit, exclude_symbol=symbol)"
            )
            return

    pytest.fail(
        "_calculate_historical_swarm no se llama desde get_master_dataframe, "
        "o get_master_dataframe no existe en features.py"
    )
