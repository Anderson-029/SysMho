---
name: sysmho-review
description: Analiza un archivo de SysMho antes de modificarlo — dependencias, tablas BD, side effects y riesgos
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

Antes de modificar cualquier archivo de SysMho, ejecuta este análisis completo de impacto.

El usuario debe indicar el archivo a revisar. Si no lo indica, pídelo.

## Paso 1 — Leer el archivo completo

Lee el archivo indicado y entiende su propósito, clases y funciones principales.

## Paso 2 — Mapa de dependencias

Encuentra qué otros módulos importan este archivo:
```bash
grep -r "from.*MODULO import\|import.*MODULO" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" -l 2>&1
```

Encuentra qué importa este archivo (sus dependencias):
```bash
grep -E "^from|^import" ARCHIVO 2>&1
```

## Paso 3 — Tablas de BD que toca

Busca todas las queries SQL en el archivo:
```bash
grep -E "SELECT|INSERT|UPDATE|DELETE|FROM|JOIN" ARCHIVO -i 2>&1
```

Para cada tabla mencionada, verifica que existe en la BD y que los campos referenciados son correctos.

## Paso 4 — Variables de entorno que necesita

```bash
grep -E "os\.getenv|os\.environ" ARCHIVO 2>&1
```

Verifica que esas variables estén definidas en `.env`.

## Paso 5 — Side effects y riesgos

Identifica:
- ¿Escribe archivos? (open, write, json.dump)
- ¿Modifica estado global? (variables globales, singletons)
- ¿Hace llamadas a Binance? (trader, exchange, ccxt)
- ¿Escribe en la BD? (INSERT, UPDATE, DELETE)
- ¿Se llama desde main.py en un loop crítico?

## Paso 6 — Reporte de impacto

Presenta:
```
ARCHIVO: nombre.py
Propósito: ...
Lo importan: módulo1.py, módulo2.py (N archivos)
Tablas BD: trades ✅, positions ✅
Env vars: BINANCE_API_KEY ✅, CB_MAX_POSITIONS ✅
Side effects: escribe a sysmho_brain.log, llama a Binance API
Riesgo de cambio: ALTO / MEDIO / BAJO
Recomendación: ...
```
