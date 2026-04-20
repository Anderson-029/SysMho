# ADR-005: X-API-Key para Autenticación del Dashboard

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

El dashboard FastAPI expone endpoints sensibles: aprobar/rechazar trades, toggle modo autónomo, reset Circuit Breaker, ver balance y posiciones. Necesitaba un mecanismo de autenticación.

SysMho es un sistema **single-admin** (solo Anderson lo usa). No hay multi-tenancy, no hay roles, no hay necesidad de gestionar múltiples sesiones.

Opciones evaluadas:
- **JWT Bearer tokens:** Estándar para SPAs multi-usuario. Requiere login endpoint, refresh tokens, expiración. Overhead innecesario para single-admin.
- **Basic Auth (usuario:contraseña):** Simple pero inseguro (contraseña en cada request). No recomendable sin HTTPS.
- **OAuth2:** Para multi-provider auth. Completamente excesivo.
- **X-API-Key header:** Un secreto estático en `.env`. Validado en middleware. Sin tokens que expirar, sin login endpoint, sin gestión de sesiones.

## Decision

Header `X-API-Key` validado en middleware FastAPI (`src/dashboard/api.py`):

```python
if DASHBOARD_API_KEY and request.headers.get("X-API-Key") != DASHBOARD_API_KEY:
    return Response(status_code=403, content="Forbidden")
```

- Si `DASHBOARD_API_KEY` está **vacío** en `.env` → acceso abierto (modo desarrollo local)
- Si está **definido** → todas las rutas (excepto `/` y `/assets/*`) requieren el header
- La clave se configura en `.env` y nunca aparece en código

## Consequences

### Positivas
- Extremadamente simple: un header estático, sin estado de sesión
- Zero overhead de gestión de tokens (no expiran, no necesitan refresh)
- Modo desarrollo abierto (sin clave) → modo producción seguro (con clave)
- Compatible con cualquier cliente HTTP (curl, Postman, navegador con extensión)

### Negativas / Trade-offs
- No soporta múltiples usuarios ni roles
- La API key es un secreto de larga vida — si se expone, hay que rotar manualmente
- Sin HTTPS, la key viaja en claro en cada request (solo usar en red local o con HTTPS proxy)

### Deuda Técnica
- Si SysMho se expone a internet (no recomendado actualmente), se necesitaría HTTPS obligatorio + rotación periódica de keys
- Para multi-usuario en el futuro: migrar a JWT con roles requeriría reescritura del middleware
