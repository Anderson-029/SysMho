"""
SysMho — Tests de Validación: Fase 6b (Autenticación Frontend).

El dashboard envía 15 llamadas fetch() a /api/* sin ningún header
de autenticación. Si DASHBOARD_API_KEY está activa en el servidor,
todas fallan con 403 y el dashboard queda roto.

Fix: función apiFetch() que inyecta X-API-Key desde localStorage,
overlay de bloqueo si no hay key, y validación contra el servidor
antes de guardarla.
"""

import re
import pytest


HTML = "src/dashboard/static/index.html"
JS   = "src/dashboard/static/assets/app.js"


def _read():
    with open(HTML, "r", encoding="utf-8") as f:
        return f.read()


def _read_js():
    with open(JS, "r", encoding="utf-8") as f:
        return f.read()


# ================================================================
# 1. Wrapper apiFetch()
# ================================================================

def test_frontend_has_apifetch_wrapper():
    """
    Todas las llamadas HTTP del dashboard deben pasar por una función
    central apiFetch() en lugar de llamar fetch() directamente.
    Está definida en app.js (no en index.html, que solo carga el script).
    """
    content = _read_js()
    assert "function apiFetch" in content or "apiFetch =" in content, (
        "app.js no define apiFetch(). "
        "Fix: añadir 'async function apiFetch(url, options = {})' que "
        "inyecte el header X-API-Key leído de localStorage."
    )


def test_apifetch_reads_key_from_localstorage():
    """
    apiFetch debe leer la key de localStorage para incluirla
    en cada petición al servidor. Implementado en app.js.
    """
    content = _read_js()
    assert "localStorage" in content, (
        "app.js no usa localStorage. "
        "Fix: en apiFetch leer la key con localStorage.getItem('sysmho_api_key')."
    )


def test_apifetch_sends_x_api_key_header():
    """
    apiFetch debe añadir el header 'X-API-Key' a cada petición.
    Sin este header el middleware del servidor devuelve 403.
    Implementado en app.js.
    """
    content = _read_js()
    assert "'X-API-Key'" in content or '"X-API-Key"' in content, (
        "app.js no incluye el header 'X-API-Key' en ninguna petición. "
        "Fix: en apiFetch, añadir headers: { 'X-API-Key': key, ...options.headers }."
    )


# ================================================================
# 2. Eliminar fetch() directos a /api/
# ================================================================

def test_no_bare_fetch_to_api_routes():
    """
    Ninguna llamada fetch('/api/...) debe quedar en el código:
    todas deben usar apiFetch() para que el header se envíe siempre.

    Un fetch() directo a /api/ bypasea el mecanismo de autenticación.
    """
    content = _read()

    # Buscar líneas con fetch directo a /api/ excluyendo las llamadas de
    # autenticación (unlockDashboard e initAuth) que pasan X-API-Key
    # explícitamente y POR DISEÑO no pueden usar apiFetch.
    lines = content.splitlines()
    bare_fetch_lines = []
    for i, line in enumerate(lines):
        if re.search(r"fetch\s*\(\s*['\`]/api/", line):
            # Excepción: llamadas de auth que pasan X-API-Key explícitamente
            # (puede estar en la misma línea o en las siguientes 3)
            window = "\n".join(lines[i:i+4])
            if "'X-API-Key'" not in window and '"X-API-Key"' not in window:
                bare_fetch_lines.append(line.strip())

    assert len(bare_fetch_lines) == 0, (
        f"Encontrados {len(bare_fetch_lines)} llamados directos fetch('/api/...) "
        "que no pasan por apiFetch():\n" + "\n".join(bare_fetch_lines) + "\n"
        "Fix: reemplazar por apiFetch('/api/... o apiFetch(`/api/..."
    )


# ================================================================
# 3. Overlay de bloqueo
# ================================================================

def test_frontend_has_lock_screen_element():
    """
    Debe existir un elemento HTML de bloqueo (overlay) que cubra
    el dashboard cuando no hay key almacenada. Sin él, el usuario
    ve el dashboard roto (errores 403 silenciosos) en lugar de una
    pantalla clara que le pida la key.
    """
    content = _read()
    assert 'id="lockScreen"' in content or "id='lockScreen'" in content, (
        "index.html no tiene elemento con id='lockScreen'. "
        "Fix: añadir un div overlay que cubra todo el dashboard "
        "y muestre un campo para ingresar la API key."
    )


def test_lock_screen_has_key_input():
    """
    El overlay de bloqueo debe tener un campo <input> donde
    el operador pueda ingresar la key.
    """
    content = _read()
    assert 'id="apiKeyInput"' in content or "id='apiKeyInput'" in content, (
        "index.html no tiene input con id='apiKeyInput' en el lock screen. "
        "Fix: añadir <input type='password' id='apiKeyInput'> dentro del lockScreen."
    )


# ================================================================
# 4. Flujo de autenticación al cargar
# ================================================================

def test_frontend_checks_localstorage_on_load():
    """
    Al cargar el dashboard, debe verificarse si ya existe una key
    en localStorage. Implementado en app.js (no en index.html).
    """
    content = _read_js()
    assert "getItem" in content, (
        "app.js no llama a localStorage.getItem(). "
        "Fix: al inicio del script, verificar si existe la key con "
        "localStorage.getItem('sysmho_api_key') y mostrar/ocultar lockScreen."
    )


def test_startlifecycles_not_called_unconditionally():
    """
    startLifecycles() no debe llamarse de forma incondicional al final
    del script. Debe llamarse SOLO después de verificar/validar la key.
    Si se llama siempre, el dashboard arranca aunque no haya key válida
    y las 15 peticiones /api/* fallan con 403.
    """
    content = _read()

    # El patrón problemático es que startLifecycles() aparezca al nivel
    # raíz del <script> (≤8 espacios de indentación).
    # Las llamadas dentro de callbacks/funciones tienen más indentación.
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped not in ("startLifecycles();", "startLifecycles()"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= 8:
            pytest.fail(
                f"startLifecycles() se llama de forma incondicional en la "
                f"línea {i+1} (indentación: {indent}). "
                "Fix: mover la llamada dentro del callback de validación de key."
            )


def test_frontend_validates_key_against_server():
    """
    Antes de guardar la key en localStorage, debe validarse contra
    el servidor haciendo una petición a /api/system/status con el
    header X-API-Key. Si el servidor responde 403, la key es inválida.

    Sin esta validación, cualquier string se guardaría como key válida
    y el dashboard quedaría bloqueado con una key incorrecta.
    """
    content = _read()
    assert "saveKey" in content or "validateKey" in content or "unlockDashboard" in content, (
        "index.html no tiene función para validar/guardar la key "
        "(saveKey, validateKey o unlockDashboard). "
        "Fix: añadir función que haga fetch a /api/system/status con la key "
        "y solo la guarde en localStorage si el servidor responde 200."
    )
