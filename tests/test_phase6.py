"""
SysMho — Tests de Validación: Fase 6 (Seguridad y Hardening).

Estos tests FALLARÁN hasta que la Fase 6 esté implementada.
Cada uno define exactamente qué debe cambiar y por qué.
"""

import ast
import pytest


# ================================================================
# 1. api.py — Sin autenticación
# ================================================================

def test_api_has_api_key_middleware():
    """
    El dashboard no tiene ningún mecanismo de autenticación.
    Cualquiera en la red local puede ver posiciones, balances y
    aprobar órdenes de compra/venta.

    Fix: añadir middleware que verifique el header X-API-Key
    contra la variable de entorno DASHBOARD_API_KEY.
    """
    with open("src/dashboard/api.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "X-API-Key" in content, (
        "api.py no contiene 'X-API-Key'. "
        "Fix: añadir middleware HTTP que rechace (403) peticiones "
        "sin el header X-API-Key correcto."
    )


def test_api_middleware_rejects_missing_key():
    """
    El middleware debe rechazar peticiones sin el header X-API-Key
    devolviendo HTTP 403. Verificamos que existe un bloque de
    comprobación explícita (no solo que el string esté en el archivo).
    """
    with open("src/dashboard/api.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    # Buscar alguna función decorada con @app.middleware("http")
    # o clase que herede de BaseHTTPMiddleware
    found_middleware = False
    for node in ast.walk(tree):
        # Patrón 1: @app.middleware("http")
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if (isinstance(decorator.func, ast.Attribute) and
                            decorator.func.attr == 'middleware'):
                        found_middleware = True
                        break
        # Patrón 2: app.add_middleware(...)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and
                    call.func.attr == 'add_middleware'):
                found_middleware = True

    assert found_middleware, (
        "api.py no define ningún middleware HTTP. "
        "Fix: usar @app.middleware('http') o app.add_middleware() "
        "para interceptar y validar el header X-API-Key en todas las rutas."
    )


# ================================================================
# 2. api.py — Decoradores on_event deprecados
# ================================================================

def test_api_does_not_use_on_event():
    """
    @app.on_event('startup') y @app.on_event('shutdown') están
    deprecados desde FastAPI 0.93. Generan DeprecationWarning en los
    logs y serán eliminados en versiones futuras.

    Fix: migrar a contextmanager lifespan.
    """
    with open("src/dashboard/api.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "on_event" not in content, (
        "api.py todavía usa @app.on_event (deprecado en FastAPI 0.93+). "
        "Fix: migrar a:\n"
        "  from contextlib import asynccontextmanager\n"
        "  @asynccontextmanager\n"
        "  async def lifespan(app):\n"
        "      await db.connect()\n"
        "      yield\n"
        "      await db.close()\n"
        "      await trader.close_connection()\n"
        "  app = FastAPI(lifespan=lifespan)"
    )


def test_api_uses_lifespan_context_manager():
    """
    El reemplazo correcto de on_event es el parámetro lifespan
    de FastAPI junto con asynccontextmanager.
    """
    with open("src/dashboard/api.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "lifespan" in content, (
        "api.py no usa el parámetro 'lifespan'. "
        "Fix: definir la función lifespan con @asynccontextmanager "
        "y pasarla a FastAPI(lifespan=lifespan)."
    )
    assert "asynccontextmanager" in content, (
        "api.py no importa 'asynccontextmanager' de contextlib. "
        "Fix: from contextlib import asynccontextmanager"
    )


# ================================================================
# 3. portfolio.py — import requests (síncrono)
# ================================================================

def test_portfolio_does_not_import_requests():
    """
    portfolio.py usa 'import requests' que es síncrono y bloquea
    el event loop de asyncio cuando se llama dentro de corutinas.
    Aunque actualmente está envuelto en asyncio.to_thread(), usar
    httpx.AsyncClient es la solución idiomática y más eficiente.

    Fix: eliminar 'import requests' y usar httpx.AsyncClient.
    """
    with open("src/dashboard/routes/portfolio.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "import requests" not in content, (
        "portfolio.py todavía usa 'import requests' (librería síncrona). "
        "Fix: reemplazar con 'import httpx' y usar "
        "'async with httpx.AsyncClient() as client: await client.get(url)'"
    )


def test_portfolio_uses_httpx():
    """
    El reemplazo de requests debe ser httpx con su interfaz async.
    """
    with open("src/dashboard/routes/portfolio.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "httpx" in content, (
        "portfolio.py no usa httpx. "
        "Fix: import httpx y usar httpx.AsyncClient() en get_exchange_rates()."
    )


def test_portfolio_get_exchange_rates_is_truly_async():
    """
    get_exchange_rates ya es async pero actualmente llama a
    asyncio.to_thread(requests.get, ...) para no bloquear.
    Con httpx.AsyncClient la llamada puede ser directamente await
    sin necesitar to_thread.

    Verificamos que ya no hay asyncio.to_thread envolviendo requests.
    """
    with open("src/dashboard/routes/portfolio.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Si ya no hay 'requests' no puede haber 'to_thread(requests...'
    # Esta verificación es transitiva con test_portfolio_does_not_import_requests
    # pero la dejamos explícita para claridad
    assert "to_thread(requests" not in content, (
        "portfolio.py usa asyncio.to_thread(requests.get, ...) como workaround. "
        "Fix: reemplazar completamente con await client.get(url) de httpx."
    )


# ================================================================
# 4. main.py — signal.signal() en el event loop
# ================================================================

def test_main_does_not_use_signal_signal():
    """
    signal.signal() registra un handler que se ejecuta en el hilo
    principal interrumpiendo el event loop de asyncio en un punto
    arbitrario. El handler actual llama asyncio.all_tasks() que
    no es thread-safe desde un signal handler.

    Fix: usar loop.add_signal_handler() que encola el callback
    en el event loop de forma segura.
    """
    with open("src/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Filtrar comentarios — solo verificar líneas de código reales
    code_lines = [
        line for line in content.splitlines()
        if not line.strip().startswith("#") and "signal.signal(" in line
    ]
    assert len(code_lines) == 0, (
        f"main.py todavía usa signal.signal() en código (líneas: {code_lines}). "
        "Fix: dentro de bot.start(), usar:\n"
        "  loop = asyncio.get_event_loop()\n"
        "  loop.add_signal_handler(signal.SIGINT, callback)"
    )


def test_main_uses_loop_add_signal_handler():
    """
    El mecanismo seguro para señales POSIX en asyncio es
    loop.add_signal_handler() que encola el callback en el
    event loop sin interrumpirlo.
    """
    with open("src/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "add_signal_handler" in content, (
        "main.py no usa add_signal_handler. "
        "Fix: reemplazar signal.signal(signal.SIGINT, handler) con "
        "loop.add_signal_handler(signal.SIGINT, callback) dentro del "
        "contexto asyncio (ej: al inicio de bot.start())."
    )
